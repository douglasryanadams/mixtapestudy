import logging

import requests
from flask import Blueprint, redirect, render_template, request, session
from werkzeug.wrappers.response import Response

from mixtapestudy.config import SPOTIFY_BASE_URL
from mixtapestudy.database import User, get_session
from mixtapestudy.errors import UserIDMissingError
from mixtapestudy.models import Song

logger = logging.getLogger(__name__)

search = Blueprint("search", __name__)


@search.route("/search")
def get_search_page() -> str:
    user_id = session.get("id")
    if not user_id:
        raise UserIDMissingError

    logger.debug("User ID from session: %s", user_id)

    search_term = request.args.get("search_term")
    search_results = []

    if search_term:
        with get_session() as db_session:
            user = db_session.get(User, user_id)
            logger.debug("User from database: %s", user)
            access_token = user.access_token

        search_response = requests.get(
            url=f"{SPOTIFY_BASE_URL}/search",
            params={"q": search_term, "type": "track", "limit": 8},
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=30,
        )
        search_response.raise_for_status()

        rjson = search_response.json()
        search_results = [
            Song(
                song["id"],
                song["name"],
                ", ".join([artist["name"] for artist in song["artists"]]),
            )
            for song in rjson["tracks"]["items"]
        ]

    selected_songs = session.get(
        "selected_songs", [{"id": None}, {"id": None}, {"id": None}]
    )
    logger.debug("  selected_songs=%s", selected_songs)
    allow_selected_songs = (
        selected_songs[0]["id"] is None
        or selected_songs[1]["id"] is None
        or selected_songs[2]["id"] is None
    )

    return render_template(
        "search.html.j2",
        search_term=search_term,
        selected_songs=selected_songs,
        search_results=search_results,
        allow_selecting_songs=allow_selected_songs,
    )


@search.route("/search/select", methods=["POST"])
def select_song() -> Response:
    user_id = session.get("id")
    if not user_id:
        raise UserIDMissingError

    selected_songs = session.get(
        "selected_songs", [{"id": None}, {"id": None}, {"id": None}]
    )
    for song in selected_songs:
        if not song["id"]:
            song["id"] = request.form.get("id")
            song["name"] = request.form.get("name")
            song["artist"] = request.form.get("artist")
            break

    session["selected_songs"] = selected_songs

    return redirect(request.referrer)


@search.route("/search/remove", methods=["POST"])
def remove_song() -> Response:
    user_id = session.get("id")
    if not user_id:
        raise UserIDMissingError

    selected_songs = session.get("selected_songs", [])
    item_index = request.form.get("index")
    selected_songs[int(item_index) - 1] = {"id": None}
    session["selected_songs"] = selected_songs

    return redirect(request.referrer)
