from flask import Blueprint

history = Blueprint("history", __name__)


def _pull_history(user_id: str | None = None) -> None: ...


@history.route("/pull", methods=["GET"])
def pull_history() -> (str, int):
    pull_history()
    return "", 204


@history.route("/pull/<user_id>", methods=["GET"])
def pull_history(user_id: str) -> (str, int):
    _pull_history(user_id)
    return "", 204
