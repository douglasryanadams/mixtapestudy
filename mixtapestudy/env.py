import logging
import os

logger = logging.getLogger(__name__)

SPOTIFY_BASE_URL = "https://api.spotify.com/v1"


class Config:
    def __init__(self):
        self._oauth_redirect_base_url: str = os.environ.get(
            "OAUTH_REDIRECT_BASE_URL", "https://mixtapestudy.com"
        )
        logger.debug(f"{self._oauth_redirect_base_url=}")

        self._spotify_client_id: str = os.environ.get(
            "SPOTIFY_CLIENT_ID", "24c831c158dc43b79f6eab9c65a38a6c"
        )
        logger.debug(f"{self._spotify_client_id=}")

        self._spotify_client_secret: str = os.environ.get("SPOTIFY_CLIENT_SECRET", "")
        if not self._spotify_client_secret:
            raise Exception("No SPOTIFY_CLIENT_SECRET environment variable provided")
        logger.debug("SPOTIFY_CLIENT_SECRET defined (not shown)")

        self._database_url: str = os.environ.get("DATABASE_URL", "")
        if not self._database_url:
            raise Exception("No DATABASE_URL environment variable provided")
        logger.debug("DATABASE_URL defined (not shown)")

    @property
    def oauth_redirect_base_url(self):
        return self._oauth_redirect_base_url

    @property
    def spotify_client_id(self):
        return self._spotify_client_id

    @property
    def spotify_client_secret(self):
        return self._spotify_client_secret

    @property
    def database_url(self):
        return self._database_url


_config: Config | None = None


def get_config() -> Config:
    global _config
    if not _config:
        _config = Config()
    return _config
