# pyright: reportPrivateUsage=false

import string
from base64 import b64encode
from collections.abc import Generator
from http import HTTPStatus
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

import pytest
from flask.testing import FlaskClient
from requests_mock import Mocker, adapter
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from mixtapestudy.config import SPOTIFY_BASE_URL
from mixtapestudy.database import User
from mixtapestudy.routes.auth import OAuthError

# Need these to be longer than 255
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
            "expires_in": 60,
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


def test_login(client: FlaskClient, fake_random_choices: str) -> None:  # noqa: ARG001
    r = client.get("/login")
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


def test_oath_callback(
    client: FlaskClient,
    session: Session,
    mock_token_request: Mocker,
    mock_me_request: Mocker,
) -> None:
    r = client.get(
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

    user = session.scalars(select(User)).one()
    assert user.id
    assert user.spotify_id == "testusername"
    assert user.display_name == "Test Display Name"
    assert user.email == "test@email.com"
    assert user.access_token == FAKE_ACCESS_TOKEN
    assert user.token_scope == "fake-scope fake-scope"  # noqa: S105
    assert user.refresh_token == FAKE_REFRESH_TOKEN


def test_oauth_twice(
    client: FlaskClient,
    session: Session,
    mock_token_request: Mocker,  # noqa: ARG001
    mock_me_request: Mocker,  # noqa: ARG001
) -> None:
    r1 = client.get(
        "/oauth-callback",
        query_string={"code": "fake-code", "state": "abcdefghijklmnop"},
    )
    assert r1.status_code == HTTPStatus.FOUND
    r2 = client.get(
        "/oauth-callback",
        query_string={"code": "fake-code", "state": "abcdefghijklmnop"},
    )
    assert r2.status_code == HTTPStatus.FOUND

    assert session.execute(select(func.count()).select_from(User)).scalar() == 1


def test_oath_callback_error(client: FlaskClient) -> None:
    with pytest.raises(OAuthError):
        client.get(
            "/oauth-callback", query_string={"code": "fake-code", "error": "fake error"}
        )
