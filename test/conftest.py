import subprocess
from base64 import b64encode
from collections.abc import Generator
from datetime import datetime, timezone
from uuid import UUID

import pytest
from flask import Flask, g
from flask.testing import FlaskClient
from freezegun import freeze_time
from loguru import logger
from pytest_socket import disable_socket
from requests_mock import Mocker, adapter
from sqlalchemy import delete
from sqlalchemy.orm import Session

from mixtapestudy.app import create_app
from mixtapestudy.database import User, get_session

FAKE_USER_ID = UUID("00000000-0000-4000-0000-000000000000")
FAKE_LISTENBRAINZ_API_KEY = "00000000-0000-4000-0000-000000000001"

# Need these to be longer than 255 characters
_STUB = (
    "%s_"
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
)
FAKE_ACCESS_TOKEN = _STUB.format("fake-access-token")
FAKE_REFRESH_TOKEN = _STUB.format("fake-refresh-token")


def pytest_runtest_setup() -> None:
    disable_socket()


@pytest.fixture(autouse=True)
def set_time() -> None:
    with freeze_time("2020-01-01"):
        yield


@pytest.fixture(autouse=True)
def set_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOG_FILE", "/dev/null")  # DEBUG logs still written to stdout
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
        ["docker", "compose", "up", "--build", "--detach", "migration_done"],  # noqa: S607
        check=True,
    )
    assert up.returncode == 0
    yield
    down = subprocess.run(  # noqa: S603
        ["docker", "compose", "down", "--volumes", "--remove-orphans"],  # noqa: S607
        check=True,
    )
    assert down.returncode == 0


@pytest.fixture(autouse=True)
def reset_database() -> None:
    yield
    with get_session() as db_session:
        db_session.execute(delete(User))


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
    with app.app_context():
        # before_request() not called on tests
        g.logger = logger.bind()
        yield app.test_client()


@pytest.fixture
def client(client_without_session: FlaskClient) -> FlaskClient:
    with get_session() as db_session:
        if not db_session.get(User, FAKE_USER_ID):
            db_session.add(
                User(
                    id=FAKE_USER_ID,
                    spotify_id="fake-spotify-id",
                    email="fake@email.com",
                    display_name="Fake Display Name",
                    access_token=FAKE_ACCESS_TOKEN,
                    token_expires=datetime(2020, 1, 1, 1, 0, 0, tzinfo=timezone.utc),
                    token_scope="fake-scope fake-scope",  # noqa: S106
                    refresh_token=FAKE_REFRESH_TOKEN,
                )
            )
            db_session.commit()

    with client_without_session.session_transaction() as tsession:
        tsession["id"] = FAKE_USER_ID
        tsession["spotify_id"] = "fake-spotify-id"

    return client_without_session  # Actually has a session now


@pytest.fixture
def mock_token_refresh(requests_mock: Mocker) -> adapter._Matcher:
    encoded_fake_auth = b64encode(
        b"fake-spotify-client-id:fake-spotify-client-secret"
    ).decode("utf8")
    return requests_mock.post(
        "https://accounts.spotify.com/api/token",
        request_headers={
            "content-type": "application/x-www-form-urlencoded",
            "Authorization": f"Basic {encoded_fake_auth}",
        },
        json={
            "access_token": f"{FAKE_ACCESS_TOKEN}_new",
            "token_type": "Bearer",
            "expires_in": 3600,
            "refresh_token": f"{FAKE_REFRESH_TOKEN}_new",
            "scope": "fake-scope fake-scope",
        },
    )
