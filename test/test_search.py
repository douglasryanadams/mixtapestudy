# pyright: reportPrivateUsage=false
import json
from http import HTTPStatus
from urllib.parse import urlencode

import pytest
from flask.testing import FlaskClient
from requests_mock import Mocker, adapter

from mixtapestudy.config import SPOTIFY_BASE_URL
from mixtapestudy.routes.search import UserIDMissingError

# TODO: Write tests to handle edge cases and errors


@pytest.fixture
def mock_search_request(requests_mock: Mocker) -> adapter._Matcher:
    return requests_mock.get(
        f"{SPOTIFY_BASE_URL}/search?{urlencode(
            {"q": "test-term", "type": "track", "limit": 8}
        )}",
        request_headers={"authorization": "Bearer fake-access-token"},
        # This is a dramatically truncated version of this response
        # For full example see:
        #   https://developer.spotify.com/documentation/web-api/reference/search
        json={
            "tracks": {
                "href": "https://api.spotify.com/v1/search?query=test-term&type=track&limit=8",
                "items": [
                    {
                        "artists": [{"name": "test-term"}, {"name": "other-artist"}],
                        "name": f"test-track-{i}",
                        "id": f"test-track-id-{i}",
                        "uri": f"spotify:track:test-track-id-{i}",
                    }
                    for i in range(8)
                ],
                "limit": 8,
                "next": "https://api.spotify.com/v1/search?query=test-term&type=track&offset=8&limit=8",
                "offset": 0,
                "previous": None,
                "total": 90,
            }
        },
    )


def test_load_without_session(client_without_session: FlaskClient) -> None:
    with pytest.raises(UserIDMissingError):
        client_without_session.get("/search")


def test_select_without_session(client_without_session: FlaskClient) -> None:
    with pytest.raises(UserIDMissingError):
        client_without_session.post("/search/select/test-track-id-1")


def test_load_empty_search_page(client: FlaskClient) -> None:
    search_page_response = client.get("/search")
    assert search_page_response.status_code == HTTPStatus.OK

    # TODO: parse html


def test_load_search_result(client: FlaskClient, mock_search_request: None) -> None:  # noqa: ARG001
    search_page_response = client.get(
        f"/search?{urlencode({"search_term": "test-term"})}"
    )
    assert search_page_response.status_code == HTTPStatus.OK

    # TODO: parse HTML for search results


def test_load_search_with_terms(client: FlaskClient) -> None:
    with client.session_transaction() as tsession:
        tsession["selected_tracks"] = json.dumps(
            [
                {
                    "id": f"test-track-id-{i}",
                    "name": f"test-track-name-{i}",
                    "artist": f"test-track-artist-{i}",
                }
                for i in range(3)
            ]
        )

    search_page_response = client.get("/search")
    assert search_page_response.status_code == HTTPStatus.OK

    # TODO: parse HTML for selected_tracks


def test_select_track(client: FlaskClient) -> None:
    with client:
        search_page_response = client.post("/search/select/test-track-id-1")
        assert search_page_response.status_code == HTTPStatus.FOUND

        # TODO: session is updated with selected track and data from Spotify API
