import logging

import requests
from flask import Blueprint, render_template, session
from requests import HTTPError

from mixtapestudy.config import SPOTIFY_BASE_URL
from mixtapestudy.database import User, get_session
from mixtapestudy.errors import MixtapeHTTPError, UserIDMissingError
from mixtapestudy.models import Song

logger = logging.getLogger(__name__)

playlist = Blueprint("playlist", __name__)


@playlist.route("/playlist/preview", methods=["POST"])
def generate_playlist() -> str:
    user_id = session.get("id")
    if not user_id:
        raise UserIDMissingError

    with get_session() as db_session:
        user = db_session.get(User, user_id)
        logger.debug("User from database: %s", user)
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
            id=song["id"],
            name=song["name"],
            artist=", ".join([artist["name"] for artist in song["artists"]]),
        )
        for song in playlist_response.json()["tracks"]
    ]

    return render_template("playlist.html.j2", playlist_songs=playlist_songs)
