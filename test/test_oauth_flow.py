import string
from pytest import fixture
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
    assert  parsed_query_params == {
        "response_type": ["code"],
        "client_id": ["fake-spotify-client-id"],
        "scope": ["playlist-modify-public playlist-modify-private user-read-recently-played user-read-currently-playing"],
        "redirect_uri": ["http://fake-test-domain/oauth-callback"],
        "state": ["abcdefghijklmnop"]
    }


