import os
import sys
from enum import StrEnum

from loguru import logger

SPOTIFY_BASE_URL = "https://api.spotify.com/v1"
USER_AGENT = "https://mixtapestudy.com/v1 ( douglas@builtonbits.com )"


class MissingEnvironmentVariableError(Exception):
    def __init__(self, variable_name: str) -> None:
        super().__init__(f"No {variable_name} environment variable provided")


class InvalidConfigurationError(Exception):
    def __init__(self, variable_name: str, valid_value: str) -> None:
        super().__init__(f"{variable_name} is not {valid_value}")


class RecommendationService(StrEnum):
    LISTENBRAINZ = "listenbrainz"
    SPOTIFY = "spotify"


class Config:
    def __init__(self) -> None:
        self._log_file: str = os.environ.get(
            "LOG_FILE", "/home/app/log/mixtapestudy.log"
        )
        logger.debug("logfile={}", self._log_file)  # Ironically

        self._oauth_redirect_base_url: str = os.environ.get(
            "OAUTH_REDIRECT_BASE_URL",
            "https://mixtapestudy.com",
        )
        logger.debug("oauth_redirect_base_url={}", self._oauth_redirect_base_url)

        self._spotify_client_id: str = os.environ.get("SPOTIFY_CLIENT_ID")
        if not self._spotify_client_id:
            raise MissingEnvironmentVariableError("SPOTIFY_CLIENT_ID")
        logger.debug("spotify_client_id={}", self._spotify_client_id)

        self._spotify_client_secret: str = os.environ.get("SPOTIFY_CLIENT_SECRET", "")
        if not self._spotify_client_secret:
            raise MissingEnvironmentVariableError("SPOTIFY_CLIENT_SECRET")
        logger.debug("SPOTIFY_CLIENT_SECRET defined (not shown)")

        self._database_url: str = os.environ.get("DATABASE_URL", "")
        if not self._database_url:
            raise MissingEnvironmentVariableError("DATABASE_URL")
        logger.debug("DATABASE_URL defined (not shown)")

        self._session_secret: str = os.getenv("SESSION_SECRET", "")
        if not self._session_secret:
            raise MissingEnvironmentVariableError("SESSION_SECRET")
        logger.debug("SESSION_SECRET defined (not shown)")

        recommendation_service_str: str = os.getenv("RECOMMENDATION_SERVICE", "spotify")
        try:
            self._recommendation_service = RecommendationService(
                recommendation_service_str
            )
        except ValueError:
            logger.error(
                "Invalid RECOMMENDATION_SERVICE, valid values: {}",
                [rs.value for rs in RecommendationService],
            )
            sys.exit(1)
        logger.debug("recommendation_service={}", self._recommendation_service)

        if self._recommendation_service == RecommendationService.LISTENBRAINZ:
            self._listenbrainz_api_key: str = os.getenv("LISTENBRAINZ_API_KEY", "")
            if not self._listenbrainz_api_key:
                raise MissingEnvironmentVariableError("LISTENBRAINZ_API_KEY")
            logger.debug("LISTENBRAINZ_API_KEY defined (not shown)")

    @property
    def log_file(self) -> str:
        return self._log_file

    @property
    def oauth_redirect_base_url(self) -> str:
        return self._oauth_redirect_base_url

    @property
    def spotify_client_id(self) -> str:
        return self._spotify_client_id

    @property
    def spotify_client_secret(self) -> str:
        return self._spotify_client_secret

    @property
    def database_url(self) -> str:
        return self._database_url

    @property
    def session_secret(self) -> str:
        return self._session_secret

    @property
    def recommendation_service(self) -> RecommendationService:
        return self._recommendation_service

    @property
    def listenbrainz_api_key(self) -> str:
        if self._recommendation_service == RecommendationService.LISTENBRAINZ:
            return self._listenbrainz_api_key
        raise InvalidConfigurationError("RECOMMENDATION_SERVICE", "listenbrainz")


_config: Config | None = None


def get_config() -> Config:
    global _config  # noqa: PLW0603
    if not _config:
        _config = Config()
    return _config
