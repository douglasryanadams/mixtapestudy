import json
import logging
from datetime import datetime, timezone
from urllib.parse import ParseResult

import requests
from flask import Blueprint, Response, redirect, render_template, request, session
from requests import HTTPError

from mixtapestudy.config import SPOTIFY_BASE_URL
from mixtapestudy.database import User, get_session
from mixtapestudy.errors import MixtapeHTTPError
from mixtapestudy.models import Song
from mixtapestudy.routes.util import get_user

logger = logging.getLogger(__name__)

playlist = Blueprint("playlist", __name__)


@playlist.route("/playlist/preview", methods=["POST"])
def generate_playlist() -> str:
    user = get_user()

    access_token = user.access_token

    selected_songs = session.get("selected_songs")
    logger.debug("  selected_songs=%s", selected_songs)

    playlist_response = requests.get(
        url=f"{SPOTIFY_BASE_URL}/recommendations",
        params={
            "seed_tracks": ",".join([song["id"] for song in selected_songs]),
            "limit": 72,
        },
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=30,
    )
    try:
        playlist_response.raise_for_status()
    except HTTPError as error:
        error.add_note("Failed to fetch song recommendations")
        error.add_note(error.response.text)
        error.add_note(error.request)
        raise MixtapeHTTPError(error) from error

    playlist_songs = [
        Song(
            uri=song["uri"],
            id=song["id"],
            name=song["name"],
            artist=song["artist"],
        )
        for song in selected_songs
    ]
    playlist_songs += [
        Song(
            uri=song["uri"],
            id=song["id"],
            name=song["name"],
            artist=", ".join([artist["name"] for artist in song["artists"]]),
        )
        for song in playlist_response.json()["tracks"]
    ]

    return render_template("playlist.html.j2", playlist_songs=playlist_songs)


@playlist.route("/playlist/save", methods=["POST"])
def save_playlist() -> str | Response:
    user = get_user()

    playlist_songs_raw = request.form.get("playlist_songs")
    logger.debug("  playlist_songs_raw=%s", playlist_songs_raw)

    playlist_songs = json.loads(playlist_songs_raw)
    playlist_name = request.form.get("playlist_name")
    playlist_uris = [song["uri"] for song in playlist_songs]

    with get_session() as db_session:
        user = db_session.get(User, user.id)
        logger.debug("User from database: %s", user)
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
