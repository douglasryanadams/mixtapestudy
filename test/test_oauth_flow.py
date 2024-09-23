import string
from base64 import b64encode

import requests_mock
from pytest import fixture, raises
from unittest.mock import patch
from urllib.parse import urlparse, parse_qs

from flask.testing import FlaskClient


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
            "playlist-modify-public playlist-modify-private user-read-recently-played user-read-currently-playing"],
        "redirect_uri": ["http://fake-test-domain/oauth-callback"],
        "state": ["abcdefghijklmnop"]
    }


def test_oath_callback(client: FlaskClient):
    with requests_mock.Mocker() as mock_requests:
        encoded_fake_auth = b64encode(b"fake-spotify-client-id:fake-spotify-client-secret").decode("utf8")
        history = mock_requests.post(
            "https://accounts.spotify.com/api/token",
            headers={"content-type": "application/x-www-form-urlencoded",
                     "Authorization": f"Basic {encoded_fake_auth}"},
            json={
                "access_token": "fake-access-token",
                "scope": "fake-scope fake-scope",
                "refresh_token": "fake-refresh-token",
                "expires_in": 60
            })

        r = client.get("/oauth-callback", query_string={'code': 'fake-code', 'state': 'abcdefghijklmnop'})
        assert r.status_code == 302
        assert r.headers["Location"] == "/search"

        assert mock_requests.called_once
        assert parse_qs(mock_requests.last_request.text) == {
            "code": ["fake-code"],
            "redirect_uri": ["http://fake-test-domain/oauth-callback"],
            "grant_type": ["authorization_code"]
        }


def test_oath_callback_error(client: FlaskClient):
    with raises(Exception):
        r = client.get("/oauth-callback", query_string={'code': 'fake-code', 'error': 'fake error'})
