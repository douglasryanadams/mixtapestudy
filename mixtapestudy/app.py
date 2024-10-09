import inspect
import logging
import sys

import flask
from flask import Flask
from loguru import logger
from requests import HTTPError

from mixtapestudy.config import get_config
from mixtapestudy.error_handlers import (
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


def create_app() -> Flask:
    config = get_config()  # Loads environment variables
    logger.add(
        config.log_file,
        level=logging.INFO,
        colorize=False,
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} "
        "| {extra[spotify_id]}:{extra[user]} "
        "| {level: <8} | {name}:{line} | {message}",
    )
    flask_app = flask.Flask(__name__)
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
    flask_app.register_error_handler(HTTPError, handle_http_request_error)
    flask_app.register_error_handler(Exception, handle_generic_errors)

    return flask_app


if __name__ == "__main__":
    app = create_app()
