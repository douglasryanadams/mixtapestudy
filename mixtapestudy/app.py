import logging
import sys

from flask import Flask

logging.basicConfig(
    level=logging.DEBUG,
    stream=sys.stdout,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
requests_logger = logging.getLogger("requests.packages.urllib3")
requests_logger.setLevel(logging.DEBUG)
requests_logger.propagate = True
logger = logging.getLogger(__name__)


def create_app():
    app = Flask(__name__)
    from mixtapestudy.routes.auth import auth
    from mixtapestudy.routes.root import root
    from mixtapestudy.routes.search import search

    app.register_blueprint(root)
    app.register_blueprint(auth)
    app.register_blueprint(search)
    return app


if __name__ == "__main__":
    app = create_app()
