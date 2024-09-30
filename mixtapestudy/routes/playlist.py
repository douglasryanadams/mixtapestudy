import logging

from flask import Blueprint, render_template, request

logger = logging.getLogger(__name__)

playlist = Blueprint("playlist", __name__)


@playlist.route("/playlist/preview", methods=["POST"])
def generate_playlist() -> str:
    selected_songs = request.form.get("selected_tracks")
    logger.debug("  selected_songs=%s", selected_songs)
    return render_template("playlist.html.j2")
