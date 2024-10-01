# pyright: reportPrivateUsage=false
from http import HTTPStatus
from urllib.parse import urlencode

import pytest
from bs4 import BeautifulSoup
from flask import session
from flask.testing import FlaskClient
from requests_mock import Mocker, adapter

from mixtapestudy.config import SPOTIFY_BASE_URL
from mixtapestudy.errors import UserIDMissingError

# TODO: Write tests to handle edge cases and errors
# TODO: Test clicking all the buttons


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
                "href": "https://api.spotify.com/v1/search?query=test-term&type=song&limit=8",
                "items": [
                    {
                        "artists": [{"name": "test-term"}, {"name": "other-artist"}],
                        "name": f"test-song-{i}",
                        "id": f"test-song-id-{i}",
                        "uri": f"spotify:song:test-song-id-{i}",
                    }
                    for i in range(8)
                ],
                "limit": 8,
                "next": "https://api.spotify.com/v1/search?query=test-term&type=song&offset=8&limit=8",
                "offset": 0,
                "previous": None,
                "total": 90,
            }
        },
    )


@pytest.mark.parametrize(
    ("method", "path"),
    [("GET", "/search"), ("POST", "/search/select"), ("POST", "/search/remove")],
)
def test_load_without_session(
    client_without_session: FlaskClient, method: str, path: str
) -> None:
    if method == "GET":
        with pytest.raises(UserIDMissingError):
            client_without_session.get(path)
    elif method == "POST":
        with pytest.raises(UserIDMissingError):
            client_without_session.post(path)
    else:
        pytest.fail(f"Unexpected method type provided: {method}")


def test_load_empty_search_page(client: FlaskClient) -> None:
    search_page_response = client.get("/search")
    assert search_page_response.status_code == HTTPStatus.OK

    soup = BeautifulSoup(search_page_response.text, features="html.parser")
    headings = soup.find_all("h2")
    assert [h.string for h in headings] == ["Selected Songs", "Search for Songs"]

    search_result_table = soup.find("table", {"id": "search-results"})
    search_result_rows = search_result_table.find_all("tr")
    assert len(search_result_rows) == 1, search_result_rows


def test_load_search_results(client: FlaskClient, mock_search_request: None) -> None:  # noqa: ARG001
    search_page_response = client.get(
        f"/search?{urlencode({"search_term": "test-term"})}"
    )
    assert search_page_response.status_code == HTTPStatus.OK

    soup = BeautifulSoup(search_page_response.text, features="html.parser")

    search_result_table = soup.find("table", {"id": "search-results"})
    search_result_rows = search_result_table.find_all("tr")
    search_page_length = 8
    assert len(search_result_rows) == search_page_length + 1, search_result_rows

    first_row = search_result_rows[1]  # [0] is the header
    first_row_cells = first_row.find_all("td")
    assert [c.string for c in first_row_cells] == [
        None,
        "test-song-0",
        "test-term, other-artist",
    ]
    last_row = search_result_rows[-1]
    last_row_cells = last_row.find_all("td")
    assert [c.string for c in last_row_cells] == [
        None,
        "test-song-7",
        "test-term, other-artist",
    ]


def test_load_search_with_selected_songs(client: FlaskClient) -> None:
    with client.session_transaction() as tsession:
        tsession["selected_songs"] = [
            {
                "id": f"test-song-id-{i}",
                "name": f"test-song-name-{i}",
                "artist": f"test-song-artist-{i}",
            }
            for i in range(3)
        ]

    search_page_response = client.get("/search")
    assert search_page_response.status_code == HTTPStatus.OK

    soup = BeautifulSoup(search_page_response.text, features="html.parser")

    selected_songs_table = soup.find("table", {"id": "selected-songs"})
    selected_songs_rows = selected_songs_table.find_all("tr")
    selected_song_limit = 3
    assert len(selected_songs_rows) == selected_song_limit, selected_songs_rows

    first_row = selected_songs_rows[0]  # [0] is the header
    first_row_cells = first_row.find_all("td")
    assert [c.string for c in first_row_cells] == [
        "1",
        "test-song-name-0 (test-song-artist-0)",
        None,
    ]

    last_row = selected_songs_rows[-1]
    last_row_cells = last_row.find_all("td")
    assert [c.string for c in last_row_cells] == [
        "3",
        "test-song-name-2 (test-song-artist-2)",
        None,
    ]


def test_select_song(client: FlaskClient) -> None:
    with client:
        search_page_response = client.post(
            "/search/select",
            data={
                "id": "test-song-id",
                "name": "test-song-name",
                "artist": "test-song-artist",
            },
        )
        assert search_page_response.status_code == HTTPStatus.FOUND
        assert session["selected_songs"] == [
            {
                "id": "test-song-id",
                "name": "test-song-name",
                "artist": "test-song-artist",
            },
            {"id": None},
            {"id": None},
        ]


def test_select_song_in_middle(client: FlaskClient) -> None:
    with client.session_transaction() as tsession:
        tsession["selected_songs"] = [
            {
                "id": f"test-song-id-{i}",
                "name": f"test-song-name-{i}",
                "artist": f"test-song-artist-{i}",
            }
            for i in range(3)
        ]
        tsession["selected_songs"][1] = {"id": None}

    with client:
        search_page_response = client.post(
            "/search/select",
            data={
                "id": "test-song-id",
                "name": "test-song-name",
                "artist": "test-song-artist",
            },
        )
        assert search_page_response.status_code == HTTPStatus.FOUND
        assert session["selected_songs"][1] == {
            "id": "test-song-id",
            "name": "test-song-name",
            "artist": "test-song-artist",
        }


def test_remove_song(client: FlaskClient) -> None:
    with client.session_transaction() as tsession:
        tsession["selected_songs"] = [
            {
                "id": f"test-song-id-{i}",
                "name": f"test-song-name-{i}",
                "artist": f"test-song-artist-{i}",
            }
            for i in range(3)
        ]

    with client:
        remove_response = client.post("/search/remove", data={"index": "2"})
        assert remove_response.status_code == HTTPStatus.FOUND
        assert session["selected_songs"][1] == {"id": None}
