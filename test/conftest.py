import subprocess
from collections.abc import Generator

import pytest
from flask import Flask
from flask.testing import FlaskClient
from sqlalchemy.orm import Session

from mixtapestudy.app import create_app
from mixtapestudy.database import get_session


@pytest.fixture(autouse=True)
def set_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OAUTH_REDIRECT_BASE_URL", "http://fake-test-domain")
    monkeypatch.setenv("SPOTIFY_CLIENT_ID", "fake-spotify-client-id")
    monkeypatch.setenv("SPOTIFY_CLIENT_SECRET", "fake-spotify-client-secret")
    monkeypatch.setenv(
        "DATABASE_URL", "postgresql://local:admin@localhost:5432/mixtapestudy"
    )
    monkeypatch.setenv("SESSION_SECRET", "FvTmLMh7")


@pytest.fixture(autouse=True, scope="session")
def stack() -> Generator[None, None, None]:
    up = subprocess.run(  # noqa: S603
        ["docker-compose", "up", "--build", "--detach", "migration_done"],  # noqa: S607
        check=True,
    )
    assert up.returncode == 0
    yield
    down = subprocess.run(  # noqa: S603
        ["docker-compose", "down", "--volumes", "--remove-orphans"],  # noqa: S607
        check=True,
    )
    assert down.returncode == 0


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    with get_session() as s:
        yield s


@pytest.fixture
def app(stack: None, set_env: None) -> Flask:  # noqa: ARG001
    flask_app = create_app()
    flask_app.config.update({"TESTING": True})  # pyright: ignore[reportUnknownMemberType]
    return flask_app


@pytest.fixture
def client(app: Flask) -> FlaskClient:
    return app.test_client()
