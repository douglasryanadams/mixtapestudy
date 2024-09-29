import logging
from dataclasses import dataclass

import requests
from flask import Blueprint, render_template, request, session

from mixtapestudy.config import SPOTIFY_BASE_URL
from mixtapestudy.database import User, get_session

logger = logging.getLogger(__name__)

search = Blueprint("search", __name__)


@dataclass(frozen=True)
class Track:
    track_id: str
    name: str
    artist: str


@search.route("/search")
def search_page() -> str:
    # TODO: Implement with Spotify API
    search_term = request.args.get("search_term")
    selected_tracks = session.get("selected_tracks")

    search_results = []

    if search_term:
        user_id = session["id"]
        with get_session() as db_session:
            user = db_session.get(User, user_id)

        search_response = requests.get(
            url=f"{SPOTIFY_BASE_URL}/search",
            params={"q": search_term, type: "track", "limit": 8},
            headers={"Authorization": f"Bearer {user['access_token']}"},
            timeout=30,
        )
        search_response.raise_for_status()

        rjson = search_response.json()
        search_results = [
            Track(track["id"], track["name"], track["artists"][0])
            for track in rjson["tracks"]["items"]
        ]

    return render_template(
        "search.html.j2",
        selected_tracks=selected_tracks,
        search_results=search_results,
    )
