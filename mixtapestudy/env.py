import logging
import os
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Config:
    oauth_redirect_base_url: str = os.environ.get(
        "OAUTH_REDIRECT_BASE_URL", "https://mixtapestudy.com"
    )
    spotify_client_id: str = os.environ.get(
        "SPOTIFY_CLIENT_ID", "24c831c158dc43b79f6eab9c65a38a6c"
    )
    spotify_client_secret: str = os.environ.get("SPOTIFY_CLIENT_SECRET", "")

    database_url: str = os.environ.get("DATABASE_URL", "")

    def __post_init__(self):
        logger.debug(f"{self.oauth_redirect_base_url=}")
        logger.debug(f"{self.spotify_client_id=}")
        if not self.spotify_client_secret:
            raise Exception("No SPOTIFY_CLIENT_SECRET environment variable provided")
        logger.debug("SPOTIFY_CLIENT_SECRET defined (not shown)")
        if not self.database_url:
            raise Exception("No DATABASE_URL environment variable provided")
        logger.debug("DATABASE_URL defined (not shown)")


_config: Config | None = None


def get_config() -> Config:
    global _config
    if not _config:
        _config = Config()
    return _config
