import logging
from dataclasses import dataclass

import requests
from flask import Blueprint, redirect, render_template, request, session
from werkzeug.wrappers.response import Response

from mixtapestudy.config import SPOTIFY_BASE_URL
from mixtapestudy.database import User, get_session

logger = logging.getLogger(__name__)

search = Blueprint("search", __name__)


@dataclass(frozen=True)
class Track:
    id: str
    name: str
    artist: str


class UserIDMissingError(Exception):
    pass


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
            Track(
                track["id"],
                track["name"],
                ", ".join([artist["name"] for artist in track["artists"]]),
            )
            for track in rjson["tracks"]["items"]
        ]

    selected_tracks = session.get(
        "selected_tracks", [{"id": None}, {"id": None}, {"id": None}]
    )
    logger.debug("  selected_tracks=%s", selected_tracks)
    allow_selected_tracks = (
        selected_tracks[0]["id"] is None
        or selected_tracks[1]["id"] is None
        or selected_tracks[2]["id"] is None
    )

    return render_template(
        "search.html.j2",
        search_term=search_term,
        selected_tracks=selected_tracks,
        search_results=search_results,
        allow_selecting_tracks=allow_selected_tracks,
    )


@search.route("/search/select", methods=["POST"])
def select_track() -> Response:
    user_id = session.get("id")
    if not user_id:
        raise UserIDMissingError

    selected_tracks = session.get(
        "selected_tracks", [{"id": None}, {"id": None}, {"id": None}]
    )
    for track in selected_tracks:
        if not track["id"]:
            track["id"] = request.form.get("id")
            track["name"] = request.form.get("name")
            track["artist"] = request.form.get("artist")
            break

    session["selected_tracks"] = selected_tracks

    return redirect(request.referrer)


@search.route("/search/remove", methods=["POST"])
def remove_track() -> Response:
    user_id = session.get("id")
    if not user_id:
        raise UserIDMissingError

    selected_tracks = session.get("selected_tracks", [])
    item_index = request.form.get("index")
    selected_tracks[int(item_index) - 1] = {"id": None}
    session["selected_tracks"] = selected_tracks

    return redirect(request.referrer)
