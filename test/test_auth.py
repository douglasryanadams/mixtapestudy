# pyright: reportPrivateUsage=false

import string
from base64 import b64encode
from collections.abc import Generator
from datetime import datetime, timezone
from http import HTTPMethod, HTTPStatus
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

import pytest
from flask import session
from flask.testing import FlaskClient
from freezegun import freeze_time
from requests_mock import Mocker, adapter
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from mixtapestudy.config import SPOTIFY_BASE_URL
from mixtapestudy.database import User
from test.conftest import FAKE_ACCESS_TOKEN, FAKE_REFRESH_TOKEN, FAKE_USER_ID

# TODO: Write tests for handling expired auth tokens


@pytest.fixture
def fake_random_choices() -> Generator[str, None, None]:
    with patch("mixtapestudy.routes.auth.secrets.choice") as mock_choice:
        mock_choice.side_effect = string.ascii_lowercase
        yield mock_choice


@pytest.fixture
def mock_token_request(
    requests_mock: Mocker,
) -> adapter._Matcher:
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
            "access_token": FAKE_ACCESS_TOKEN,
            "scope": "fake-scope fake-scope",
            "refresh_token": FAKE_REFRESH_TOKEN,
            "expires_in": 3600,
        },
    )


@pytest.fixture
def mock_me_request(requests_mock: Mocker) -> adapter._Matcher:
    return requests_mock.get(
        f"{SPOTIFY_BASE_URL}/me",
        request_headers={
            "authorization": f"Bearer {FAKE_ACCESS_TOKEN}",
        },
        json={
            "country": "US",
            "display_name": "Test Display Name",
            "email": "test@email.com",
            "explicit_content": {
                "filter_enabled": False,
                "filter_locked": False,
            },
            "external_urls": {
                "spotify": "https://open.spotify.com/user/testusername",
            },
            "followers": {
                "href": None,
                "total": 4,
            },
            "href": "https://api.spotify.com/v1/users/testusername",
            "id": "testusername",
            "images": [
                {
                    "url": "https://scontent-atl3-2.xx.fbcdn.net/v/t39.30808-1/438204840_3812596065627877_5829513670243189444_n.jpg?stp=cp0_dst-jpg_s50x50&_nc_cat=105&ccb=1-7&_nc_sid=6738e8&_nc_ohc=gwWQdmt98PgQ7kNvgH4qeqx&_nc_ht=scontent-atl3-2.xx&edm=AP4hL3IEAAAA&oh=00_AYAmPyw01cZLO3X4BqWaBspuzfJAUcZBWUGoV0p9JU1WGQ&oe=66F72715",
                    "height": 64,
                    "width": 64,
                },
                {
                    "url": "https://scontent-atl3-2.xx.fbcdn.net/v/t39.30808-1/438204840_3812596065627877_5829513670243189444_n.jpg?stp=dst-jpg_s320x320&_nc_cat=105&ccb=1-7&_nc_sid=3e9727&_nc_ohc=gwWQdmt98PgQ7kNvgH4qeqx&_nc_ht=scontent-atl3-2.xx&edm=AP4hL3IEAAAA&oh=00_AYDhoFRkUWcWVmAvt6QY7sWRalTHdNg7tetFJIToksfjPg&oe=66F72715",
                    "height": 300,
                    "width": 300,
                },
            ],
            "product": "premium",
            "type": "user",
            "uri": "spotify:user:testusername",
        },
    )


def test_login(client_without_session: FlaskClient, fake_random_choices: str) -> None:  # noqa: ARG001
    r = client_without_session.get("/login")
    assert r.status_code == HTTPStatus.FOUND
    assert "https://accounts.spotify.com/authorize?" in r.headers["Location"]

    location_url = r.headers["Location"]
    parts = urlparse(location_url)
    parsed_query_params = parse_qs(parts.query, strict_parsing=True)
    assert parsed_query_params == {
        "response_type": ["code"],
        "client_id": ["fake-spotify-client-id"],
        "scope": [
            # Note: This is one string, not a list of strings
            "playlist-modify-public "
            "playlist-modify-private "
            "user-read-recently-played "
            "user-read-currently-playing "
            "user-read-email"
        ],
        "redirect_uri": ["http://fake-test-domain/oauth-callback"],
        "state": ["abcdefghijklmnop"],
    }


def test_oauth_callback(
    client_without_session: FlaskClient,
    db_session: Session,
    mock_token_request: Mocker,
    mock_me_request: Mocker,
) -> None:
    with client_without_session:
        r = client_without_session.get(
            "/oauth-callback",
            query_string={"code": "fake-code", "state": "abcdefghijklmnop"},
        )

        assert r.status_code == HTTPStatus.FOUND
        assert r.headers["Location"] == "/search"

        assert mock_token_request.called
        assert mock_token_request.last_request
        assert parse_qs(mock_token_request.last_request.text) == {
            "code": ["fake-code"],
            "redirect_uri": ["http://fake-test-domain/oauth-callback"],
            "grant_type": ["authorization_code"],
        }

        assert mock_me_request.called

        user = db_session.scalars(select(User)).one()
        assert user.id
        assert user.spotify_id == "testusername"
        assert user.display_name == "Test Display Name"
        assert user.email == "test@email.com"
        assert user.access_token == FAKE_ACCESS_TOKEN
        assert user.token_scope == "fake-scope fake-scope"  # noqa: S105
        assert user.token_expires == datetime(2020, 1, 1, 1, 0, 0, tzinfo=timezone.utc)
        assert user.refresh_token == FAKE_REFRESH_TOKEN

        assert session["id"] == user.id
        assert session["display_name"] == "Test Display Name"


def test_oauth_twice(
    client_without_session: FlaskClient,
    db_session: Session,
    mock_token_request: adapter._Matcher,  # noqa: ARG001
    mock_me_request: adapter._Matcher,  # noqa: ARG001
) -> None:
    with client_without_session:
        r1 = client_without_session.get(
            "/oauth-callback",
            query_string={"code": "fake-code", "state": "abcdefghijklmnop"},
        )
        assert r1.status_code == HTTPStatus.FOUND
        assert session["id"]

    with client_without_session:
        r2 = client_without_session.get(
            "/oauth-callback",
            query_string={"code": "fake-code", "state": "abcdefghijklmnop"},
        )
        assert r2.status_code == HTTPStatus.FOUND
        assert session["id"]

    assert db_session.execute(select(func.count()).select_from(User)).scalar() == 1


def test_login_again_with_existing_session(
    client_without_session: FlaskClient,
    fake_random_choices: str,  # noqa: ARG001
) -> None:
    with client_without_session.session_transaction() as tsession:
        tsession["test-session-data"] = "test-value"

    with client_without_session:
        r = client_without_session.get("/login")
        assert r.status_code == HTTPStatus.FOUND
        # Confirms that session was reset on re-auth
        assert not session.get("test-session-data")


def test_oauth_callback_error(client_without_session: FlaskClient) -> None:
    r = client_without_session.get(
        "/oauth-callback", query_string={"code": "fake-code", "error": "fake error"}
    )
    assert r.status_code == HTTPStatus.INTERNAL_SERVER_ERROR


def test_logout(client: FlaskClient) -> None:
    with client.session_transaction() as tsession:
        tsession["other"] = "other session data"

    with client:
        r = client.get("/logout")

        assert r.status_code == HTTPStatus.FOUND
        assert r.headers["Location"] == "/"
        assert not session.get("id")
        assert not session.get("other")


@pytest.mark.parametrize(
    ("method", "url", "http_code"),
    [
        (HTTPMethod.GET, "/", 200),
        (HTTPMethod.GET, "/info", 500),
        (HTTPMethod.GET, "/flask-health-check", 200),
        (HTTPMethod.GET, "/login", 302),
        (HTTPMethod.GET, "/logout", 302),
        (HTTPMethod.GET, "/oauth-callback", 500),
        (HTTPMethod.GET, "/search", 302),
        (HTTPMethod.POST, "/search/select", 302),
        (HTTPMethod.POST, "/search/remove", 302),
        (HTTPMethod.POST, "/playlist/preview", 302),
        (HTTPMethod.POST, "/playlist/save", 302),
    ],
)
def test_authorization(
    method: HTTPMethod,
    url: str,
    http_code: int,
    client_without_session: FlaskClient,
) -> None:
    func = lambda _: pytest.fail(f"Unexpected method: {method}")  # noqa: E731
    match method:
        case HTTPMethod.GET:
            func = client_without_session.get
        case HTTPMethod.POST:
            func = client_without_session.post
    r = func(url)
    assert r.status_code == http_code


def test_token_refresh(
    client: FlaskClient, mock_token_refresh: adapter._Matcher
) -> None:
    """Test of integration with get_user and one method."""
    with client.session_transaction() as tsession:
        tsession["id"] = FAKE_USER_ID
        tsession["display_name"] = "Test Name"

    with freeze_time("2020-01-01 02:00:00"):
        client.get("/search")

    assert mock_token_refresh.called
