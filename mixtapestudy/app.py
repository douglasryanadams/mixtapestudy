import inspect
import logging
import sys
from urllib.parse import urlparse

import flask
import sentry_sdk
from flask import Flask, g, session
from loguru import logger
from requests import HTTPError
from sentry_sdk.types import Event, Hint
from werkzeug.exceptions import MethodNotAllowed, NotFound

from mixtapestudy.config import get_config
from mixtapestudy.error_handlers import (
    handle_404_not_found,
    handle_dev_null_bots,
    handle_generic_errors,
    handle_http_request_error,
    handle_user_id_missing,
    handle_user_missing,
)
from mixtapestudy.errors import UserDatabaseRowMissingError, UserIDMissingError


class InterceptHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        # Get corresponding Loguru level if it exists.
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        # Find caller from where originated the logged message.
        frame, depth = inspect.currentframe(), 0
        while frame and (depth == 0 or frame.f_code.co_filename == logging.__file__):
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(
            level, record.getMessage()
        )


# https://loguru.readthedocs.io/en/stable/api/logger.html#record
logger.remove()
logger.configure(extra={"spotify_id": "-", "user": "-"})
logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)
logger.add(
    sys.stdout,
    colorize=True,
    format="<level>{level: <8}</level> "
    "| <light-blue>{extra[spotify_id]}</light-blue>"
    ":<light-green>{extra[user]}</light-green> "
    "| <yellow>{name}:{line}</yellow> "
    "| <level>{message}</level>",
)

requests_logger = logging.getLogger("requests.packages.urllib3")
requests_logger.setLevel(logging.DEBUG)
requests_logger.propagate = True

sqlalchemy_logger = logging.getLogger("sqlalchemy.engine")
sqlalchemy_logger.setLevel(logging.DEBUG)
sqlalchemy_logger.propagate = True


def filter_healthchecks(event: Event, _: Hint) -> Event:
    url_string = event["request"]["url"]
    parsed_url = urlparse(url_string)

    if parsed_url.path == "/health-check":
        return None

    if parsed_url.path == "/flask-health-check":
        return None

    return event


def create_app() -> Flask:
    config = get_config()  # Loads environment variables
    logger.add(
        config.log_file,
        level=logging.INFO,
        colorize=False,
        rotation="500 MB",
        retention=10,
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} "
        "| {extra[spotify_id]}:{extra[user]} "
        "| {level: <8} | {name}:{line} | {message}",
    )

    sentry_sdk.init(
        sample_rate=0.5,
        traces_sample_rate=0.1,
        profiles_sample_rate=0.1,
        before_send_transaction=filter_healthchecks,
    )

    flask_app = flask.Flask(__name__)

    @flask_app.before_request
    def before_request() -> None:
        if "id" in session and "spotify_id" in session:
            user_id = str(session["id"])[24:]
            spotify_id = session["spotify_id"][:8]
            g.logger = logger.bind(spotify_id=spotify_id, user=user_id)
        else:
            g.logger = logger.bind()

    from mixtapestudy.routes.auth import auth
    from mixtapestudy.routes.playlist import playlist
    from mixtapestudy.routes.root import root
    from mixtapestudy.routes.search import search

    flask_app.secret_key = get_config().session_secret
    flask_app.register_blueprint(root)
    flask_app.register_blueprint(auth)
    flask_app.register_blueprint(search)
    flask_app.register_blueprint(playlist)

    flask_app.register_error_handler(UserIDMissingError, handle_user_id_missing)
    flask_app.register_error_handler(UserDatabaseRowMissingError, handle_user_missing)
    flask_app.register_error_handler(NotFound, handle_404_not_found)
    flask_app.register_error_handler(MethodNotAllowed, handle_dev_null_bots)
    flask_app.register_error_handler(HTTPError, handle_http_request_error)
    flask_app.register_error_handler(Exception, handle_generic_errors)

    return flask_app


if __name__ == "__main__":
    app = create_app()
