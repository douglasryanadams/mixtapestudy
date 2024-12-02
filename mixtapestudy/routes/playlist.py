import json
import re
import time
from datetime import datetime, timezone
from http.client import BAD_REQUEST
from urllib.parse import ParseResult

import requests
from flask import Blueprint, Response, g, redirect, render_template, request, session

from mixtapestudy.config import (
    SPOTIFY_BASE_URL,
    USER_AGENT,
    RecommendationService,
    get_config,
)
from mixtapestudy.database import User, get_session
from mixtapestudy.models import Song
from mixtapestudy.routes.util import get_user

playlist = Blueprint("playlist", __name__)


def _get_spotify_recommendations(
    selected_songs: dict[str, str], access_token: str
) -> list[Song]:
    g.logger.debug("  selected_songs={}", selected_songs)

    playlist_response = requests.get(
        url=f"{SPOTIFY_BASE_URL}/recommendations",
        params={
            "seed_tracks": ",".join([song["id"] for song in selected_songs]),
            "limit": 72,
        },
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=30,
    )
    playlist_response.raise_for_status()

    playlist_songs = [
        Song(
            uri=song["uri"],
            id=song["id"],
            name=song["name"],
            artist=song["artist"],
            artist_raw=song["artist_raw"],
        )
        for song in selected_songs
    ]
    playlist_songs += [
        Song(
            uri=song["uri"],
            id=song["id"],
            name=song["name"],
            artist=", ".join([artist["name"] for artist in song["artists"]]),
            artist_raw=[artist["name"] for artist in song["artists"]],
        )
        for song in playlist_response.json()["tracks"]
    ]

    return playlist_songs


def _get_good_radio_response(
    listenbrainz_api_key: str, selected_songs: dict[str, str]
) -> Response:
    # There might be a cleaner way to do this, I wanted to avoid recursion and
    # prevent a potential infinite loop.
    artists = []
    for song in selected_songs:
        artists += json.loads(song["artist_raw"])

    radio_response = None

    for _ in range(30):
        g.logger.debug("  artists: {}", artists)
        prompt_string = " ".join([f"artist:({artist})" for artist in artists])

        radio_response = requests.get(
            url="https://api.listenbrainz.org/1/explore/lb-radio",
            params={"mode": "easy", "prompt": prompt_string},
            headers={"Authorization": f"Bearer {listenbrainz_api_key}"},
            timeout=30,
        )
        try:
            radio_response.raise_for_status()
            break
        except requests.exceptions.HTTPError as error:
            if error.response.status_code != BAD_REQUEST:
                raise

            error_response = error.response.json()
            g.logger.debug(" failed to retrieve lb-radio: {} {}", error, error_response)
            error_message = error_response["error"]
            artist_name_search = re.search(
                "Artist (.+) could not be looked up.", error_message
            )

            if artist_name_search:
                bad_artist = artist_name_search.group(1)
                artists = [artist for artist in artists if artist != bad_artist]

            if not artists:
                raise

    if radio_response:
        radio_response.raise_for_status()

    return radio_response


def _get_listenbrainz_radio(
    selected_songs: dict[str, str], listenbrainz_api_key: str, spotify_access_token: str
) -> list[Song]:
    radio_response = _get_good_radio_response(listenbrainz_api_key, selected_songs)

    mbids = [
        track["identifier"][0].split("/")[-1]
        for track in radio_response.json()["payload"]["jspf"]["playlist"]["track"]
    ]

    spotify_tracks = []
    rate_limit_remaining = 900  # Arbitrary > 0 number
    rate_limit_max = 1000  # Slightly larger arbitrary > 0 number

    for mbid in mbids:
        time.sleep((rate_limit_max - rate_limit_remaining) / 1000)

        # https://musicbrainz.org/doc/MusicBrainz_API#Lookups
        mb_recording = requests.get(
            url=f"https://musicbrainz.org/ws/2/recording/{mbid}",
            params={"fmt": "json", "inc": "isrcs artists"},
            headers={"User-Agent": USER_AGENT},
            timeout=30,
        )
        mb_recording.raise_for_status()

        recording_json = mb_recording.json()
        rate_limit_remaining = int(mb_recording.headers["X-RateLimit-Remaining"])
        rate_limit_max = int(mb_recording.headers["X-RateLimit-Limit"])
        isrcs = recording_json["isrcs"]
        artist_credit = recording_json["artist-credit"]

        if isrcs:
            query_string = f"isrc:{isrcs[0]}"
        else:
            query_string = f'track:{recording_json["title"]}'
            if artist_credit:
                query_string += " " + " ".join(
                    [
                        f'artist:{artist["artist"]["name"]}'
                        for artist in artist_credit[:3]
                    ]
                )

        g.logger.debug("query_string: {}", query_string)

        # https://developer.spotify.com/documentation/web-api/reference/search
        spotify_search = requests.get(
            url=f"{SPOTIFY_BASE_URL}/search",
            params={"type": "track", "q": query_string},
            headers={"Authorization": f"Bearer {spotify_access_token}"},
            timeout=30,
        )
        spotify_search.raise_for_status()

        spotify_json = spotify_search.json()
        if spotify_json["tracks"] and spotify_json["tracks"]["items"]:
            spotify_tracks.append(spotify_json["tracks"]["items"][0])

    playlist_songs = [
        Song(
            uri=song["uri"],
            id=song["id"],
            name=song["name"],
            artist=song["artist"],
            artist_raw=song["artist_raw"],
        )
        for song in selected_songs
    ]

    # This is slightly sub-optimal since we loop through tracks above,
    # but it's a small list and this is much easier to think about
    # if everything's taken care of above
    playlist_songs += [
        Song(
            uri=song["uri"],
            id=song["id"],
            name=song["name"],
            artist=", ".join([artist["name"] for artist in song["artists"]]),
            artist_raw=[artist["name"] for artist in song["artists"]],
        )
        for song in spotify_tracks
    ]
    g.logger.debug(playlist_songs)

    return playlist_songs


@playlist.route("/playlist/preview", methods=["POST"])
def generate_playlist() -> str:
    config = get_config()
    selected_songs = session.get("selected_songs")
    g.logger.debug(" selected_songs={}", selected_songs)

    user = get_user()
    access_token = user.access_token

    match config.recommendation_service:
        case RecommendationService.SPOTIFY:
            playlist_songs = _get_spotify_recommendations(selected_songs, access_token)
        case RecommendationService.LISTENBRAINZ:
            playlist_songs = _get_listenbrainz_radio(
                selected_songs, config.listenbrainz_api_key, access_token
            )

    return render_template("playlist.html.j2", playlist_songs=playlist_songs)


@playlist.route("/playlist/save", methods=["POST"])
def save_playlist() -> str | Response:
    user = get_user()

    playlist_songs_raw = request.form.get("playlist_songs")
    g.logger.debug("  playlist_songs_raw={}", playlist_songs_raw)

    playlist_songs = json.loads(playlist_songs_raw)
    playlist_name = request.form.get("playlist_name")
    playlist_uris = [song["uri"] for song in playlist_songs]

    with get_session() as db_session:
        user = db_session.get(User, user.id)
        g.logger.debug("User from database: {}", user)
        spotify_id = user.spotify_id
        access_token = user.access_token

    create_playlist_response = requests.post(
        f"{SPOTIFY_BASE_URL}/users/{spotify_id}/playlists",
        headers={"Authorization": f"Bearer {access_token}"},
        json={
            "name": f"{playlist_name} ({datetime.now(timezone.utc):%Y-%m-%d %H:%M:%S})",
            "description": "Generated by mixtapestudy.com",
            "public": True,
            "collaborative": False,
        },
        timeout=30,
    )
    create_playlist_response.raise_for_status()
    playlist_id = create_playlist_response.json()["id"]

    add_songs_response = requests.post(
        f"{SPOTIFY_BASE_URL}/playlists/{playlist_id}/tracks",
        headers={"Authorization": f"Bearer {access_token}"},
        json={"uris": playlist_uris},
        timeout=30,
    )
    add_songs_response.raise_for_status()

    playlist_url = ParseResult(
        scheme="https",
        netloc="open.spotify.com",
        path=f"/playlist/{playlist_id}",
        params="",
        query="",
        fragment="",
    ).geturl()

    return redirect(playlist_url)
