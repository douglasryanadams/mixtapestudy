import logging
from dataclasses import dataclass

from flask import Blueprint, render_template

logger = logging.getLogger(__name__)

search = Blueprint("search", __name__)


@dataclass(frozen=True)
class Track:
    name: str
    artist: str


@search.route("/search")
def search_page() -> str:
    # TODO: Implement with Spotify API
    tracks = [
        Track("Track 1", "Artist 1"),
        Track("Track 2", "Artist 2"),
        Track("Track 3", "Artist 3"),
    ]

    return render_template(
        "search.html.j2",
        selected_tracks=tracks,
        search_results=tracks,
    )
