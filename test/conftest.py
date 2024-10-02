import subprocess
from collections.abc import Generator
from uuid import UUID

import pytest
from flask import Flask
from flask.testing import FlaskClient
from freezegun import freeze_time
from sqlalchemy.orm import Session

from mixtapestudy.app import create_app
from mixtapestudy.database import User, get_session

FAKE_USER_ID = UUID("7061fb8a-5680-44b2-86c9-17a008df0be2")


@pytest.fixture(autouse=True)
def set_time() -> None:
    with freeze_time("2020-01-01"):
        yield


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
    with get_session() as sesh, sesh.begin():
        yield sesh


@pytest.fixture
def app(stack: None, set_env: None) -> Flask:  # noqa: ARG001
    flask_app = create_app()
    flask_app.config.update({"TESTING": True})  # pyright: ignore[reportUnknownMemberType]
    return flask_app


@pytest.fixture
def client_without_session(app: Flask) -> FlaskClient:
    return app.test_client()


@pytest.fixture
def client(client_without_session: FlaskClient, db_session: Session) -> FlaskClient:
    if not db_session.get(User, FAKE_USER_ID):
        db_session.add(
            User(
                id=FAKE_USER_ID,
                spotify_id="fake-spotify-id",
                email="fake@email.com",
                display_name="Fake Display Name",
                access_token="fake-access-token",  # noqa: S106
                token_scope="fake-scope fake-scope",  # noqa: S106
                refresh_token="fake-refresh-token",  # noqa: S106
            )
        )
        db_session.commit()

    with client_without_session.session_transaction() as tsession:
        tsession["id"] = FAKE_USER_ID

    return client_without_session  # Actually has a session now
