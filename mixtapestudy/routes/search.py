import logging
from dataclasses import dataclass
from urllib.parse import urlencode

import requests
from flask import Blueprint, redirect, render_template, request, session
from markupsafe import escape
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

    selected_tracks = session.get("selected_tracks", [])

    return render_template(
        "search.html.j2",
        selected_tracks=selected_tracks,
        search_results=search_results,
    )


@search.route("/search/select/<string:track_id>", methods=["POST"])
def select_track(track_id: str) -> Response:
    user_id = session.get("id")
    if not user_id:
        raise UserIDMissingError

    safe_track_id = escape(track_id)  # noqa: F841  TODO

    with get_session() as db_session:
        user = db_session.get(User, user_id)  # noqa: F841  TODO

    # TODO: Fetch track data, add to session

    search_term = request.args.get("search_term")
    if search_term:
        return redirect("/search?" + urlencode({"search_term": search_term}))

    return redirect("/search")
