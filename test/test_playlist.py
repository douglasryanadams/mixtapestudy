from urllib.parse import urlencode

import pytest
from bs4 import BeautifulSoup
from flask.testing import FlaskClient
from requests_mock import Mocker, adapter

from mixtapestudy.config import SPOTIFY_BASE_URL
from mixtapestudy.errors import UserIDMissingError

# TODO: Tests for edge cases


@pytest.fixture
def mock_recommendation_request(requests_mock: Mocker) -> adapter._Matcher:
    return requests_mock.get(
        f"{SPOTIFY_BASE_URL}/recommendations?{urlencode(
            {"seed_tracks": ",".join([f"song-{i}" for i in range(3)]), "limit": 72}
        )}",
        request_headers={"Authorization": "Bearer fake-access-token"},
        json={
            # This is a dramatically simplified version of this response
            # For full example see:
            #   https://developer.spotify.com/documentation/web-api/reference/get-recommendations
            "tracks": [
                {
                    "uri": f"spotify:song;song-{i}",
                    "id": f"song-{i}",
                    "name": f"name-{i}",
                    "artists": [{"name": f"artist-{i}-{k}"} for k in range(3)],
                }
                for i in range(72)
            ]
        },
    )


def test_load_without_session(client_without_session: FlaskClient) -> None:
    with pytest.raises(UserIDMissingError):
        client_without_session.post("/playlist/preview")


def test_load_page(
    client: FlaskClient, mock_recommendation_request: adapter._Matcher
) -> None:
    with client.session_transaction() as tsession:
        tsession["selected_songs"] = [
            {"id": f"song-{i}", "name": f"name-{i}", "artist": f"artist-{i}"}
            for i in range(3)
        ]

    playlist_page_response = client.post("/playlist/preview")

    assert mock_recommendation_request.called

    soup = BeautifulSoup(playlist_page_response.text, "html.parser")
    table_rows = soup.find_all("tr")
    number_of_songs = 72
    assert len(table_rows) == number_of_songs + 1  # Extra row for header

    first_row = table_rows[1].find_all("td")
    assert [c.string for c in first_row] == [
        "name-0",
        "artist-0-0, artist-0-1, artist-0-2",
    ]

    last_row = table_rows[-1].find_all("td")
    assert [c.string for c in last_row] == [
        "name-71",
        "artist-71-0, artist-71-1, artist-71-2",
    ]
