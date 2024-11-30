import json
from datetime import datetime, timezone
from urllib.parse import ParseResult

import requests
from flask import Blueprint, Response, g, redirect, render_template, request, session

from mixtapestudy.config import SPOTIFY_BASE_URL, RecommendationService, get_config
from mixtapestudy.database import User, get_session
from mixtapestudy.models import Song
from mixtapestudy.routes.util import get_user

playlist = Blueprint("playlist", __name__)


def _get_spotify_recommendations(selected_songs: dict[str, str]) -> list[Song]:
    user = get_user()

    access_token = user.access_token

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
            artist_raw=json.dumps([artist["name"] for artist in song["artists"]]),
        )
        for song in playlist_response.json()["tracks"]
    ]

    return playlist_songs


def _get_listenbrainz_radio(selected_songs: dict[str, str]) -> list[Song]:
    artists = []
    for song in selected_songs:
        artists += json.loads(song["artist_raw"])
    g.logger.debug("  artists: {}", artists)
    query_string = " ".join([f"artist:({artist})" for artist in artists])
    radio_response = requests.get(
        url="https://api.listenbrainz.org/1/explore/lb-radio",
        params={"mode": "easy", "query": query_string},
        # TODO: Add token header
        timeout=30,
    )
    radio_response.raise_for_status()

    playlist_songs = [
        Song(
            uri=track["identifier"],
            id=track["identifier"].split("/")[-1],
            name=track["title"],
            artist=track["creator"],
            artist_raw=json.dumps([track["creator"]]),
        )
        for track in radio_response.json()["payload"]["jspf"]["playlist"]["track"]
    ]
    g.logger.debug(playlist_songs)

    return playlist_songs


@playlist.route("/playlist/preview", methods=["POST"])
def generate_playlist() -> str:
    config = get_config()
    selected_songs = session.get("selected_songs")

    match config.recommendation_service:
        case RecommendationService.SPOTIFY:
            playlist_songs = _get_spotify_recommendations(selected_songs)
        case RecommendationService.LISTENBRAINZ:
            playlist_songs = _get_listenbrainz_radio(selected_songs)

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
