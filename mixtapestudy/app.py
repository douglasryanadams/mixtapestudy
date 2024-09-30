import logging
import sys

import flask
from flask import Flask

from mixtapestudy.config import get_config

logging.basicConfig(
    level=logging.DEBUG,
    stream=sys.stdout,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
requests_logger = logging.getLogger("requests.packages.urllib3")
requests_logger.setLevel(logging.DEBUG)
requests_logger.propagate = True

sqlalchemy_logger = logging.getLogger("sqlalchemy.engine")
sqlalchemy_logger.setLevel(logging.DEBUG)
sqlalchemy_logger.propagate = True

logger = logging.getLogger(__name__)


def create_app() -> Flask:
    get_config()  # Loads environment variables
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
    return flask_app


if __name__ == "__main__":
    app = create_app()
