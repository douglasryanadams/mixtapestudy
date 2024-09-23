import string
from base64 import b64encode

import requests_mock
from freezegun import freeze_time
from pytest import fixture, raises
from unittest.mock import patch
from urllib.parse import urlparse, parse_qs

from flask.testing import FlaskClient
from sqlalchemy import select

from mixtapestudy.database import get_session, User
from mixtapestudy.env import SPOTIFY_BASE_URL


@fixture
def fake_random_choices():
    with patch("mixtapestudy.routes.auth.random.choice") as mock_choice:
        mock_choice.side_effect = string.ascii_lowercase
        yield mock_choice


def test_login(client: FlaskClient, fake_random_choices):
    r = client.get("/login")
    assert r.status_code == 302
    assert "https://accounts.spotify.com/authorize?" in r.headers["Location"]

    location_url = r.headers["Location"]
    parts = urlparse(location_url)
    parsed_query_params = parse_qs(parts.query, strict_parsing=True)
    assert parsed_query_params == {
        "response_type": ["code"],
        "client_id": ["fake-spotify-client-id"],
        "scope": [
            "playlist-modify-public playlist-modify-private user-read-recently-played user-read-currently-playing user-read-email"],
        "redirect_uri": ["http://fake-test-domain/oauth-callback"],
        "state": ["abcdefghijklmnop"]
    }


@freeze_time("1970-01-01")
def test_oath_callback(client: FlaskClient):
    with requests_mock.Mocker() as mock_requests:
        encoded_fake_auth = b64encode(b"fake-spotify-client-id:fake-spotify-client-secret").decode("utf8")
        mock_token_request = mock_requests.post(
            "https://accounts.spotify.com/api/token",
            headers={"content-type": "application/x-www-form-urlencoded",
                     "Authorization": f"Basic {encoded_fake_auth}"},
            json={
                "access_token": "fake-access-token",
                "scope": "fake-scope fake-scope",
                "refresh_token": "fake-refresh-token",
                "expires_in": 60
            }
        )

        mock_me_request = mock_requests.get(f"{SPOTIFY_BASE_URL}/me", json={
            "country": "US",
            "display_name": "Test Display Name",
            "email": "test@email.com",
            "explicit_content": {
                "filter_enabled": False,
                "filter_locked": False
            },
            "external_urls": {
                "spotify": "https://open.spotify.com/user/testusername"
            },
            "followers": {
                "href": None,
                "total": 4
            },
            "href": "https://api.spotify.com/v1/users/testusername",
            "id": "testusername",
            "images": [
                {
                    "url": "https://scontent-atl3-2.xx.fbcdn.net/v/t39.30808-1/438204840_3812596065627877_5829513670243189444_n.jpg?stp=cp0_dst-jpg_s50x50&_nc_cat=105&ccb=1-7&_nc_sid=6738e8&_nc_ohc=gwWQdmt98PgQ7kNvgH4qeqx&_nc_ht=scontent-atl3-2.xx&edm=AP4hL3IEAAAA&oh=00_AYAmPyw01cZLO3X4BqWaBspuzfJAUcZBWUGoV0p9JU1WGQ&oe=66F72715",
                    "height": 64,
                    "width": 64
                },
                {
                    "url": "https://scontent-atl3-2.xx.fbcdn.net/v/t39.30808-1/438204840_3812596065627877_5829513670243189444_n.jpg?stp=dst-jpg_s320x320&_nc_cat=105&ccb=1-7&_nc_sid=3e9727&_nc_ohc=gwWQdmt98PgQ7kNvgH4qeqx&_nc_ht=scontent-atl3-2.xx&edm=AP4hL3IEAAAA&oh=00_AYDhoFRkUWcWVmAvt6QY7sWRalTHdNg7tetFJIToksfjPg&oe=66F72715",
                    "height": 300,
                    "width": 300
                }
            ],
            "product": "premium",
            "type": "user",
            "uri": "spotify:user:testusername"
        })

        r = client.get("/oauth-callback", query_string={'code': 'fake-code', 'state': 'abcdefghijklmnop'})

        assert r.status_code == 302
        assert r.headers["Location"] == "/search"

        assert mock_token_request.called_once
        assert parse_qs(mock_token_request.last_request.text) == {
            "code": ["fake-code"],
            "redirect_uri": ["http://fake-test-domain/oauth-callback"],
            "grant_type": ["authorization_code"]
        }

        assert mock_me_request.called_once

        actual = None
        with get_session() as session:
            user = session.scalars(select(User)).one()
            assert user.id
            assert user.spotify_id == 'testusername'
            assert user.display_name == 'Test Display Name'
            assert user.email == 'test@email.com'
            assert user.access_token == 'fake-access-token'
            assert user.token_scope == 'fake-scope fake-scope'
            assert user.refresh_token == 'fake-refresh-token'


def test_oath_callback_error(client: FlaskClient):
    with raises(Exception):
        client.get("/oauth-callback", query_string={'code': 'fake-code', 'error': 'fake error'})
