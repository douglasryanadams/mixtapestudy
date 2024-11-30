# pyright: reportPrivateUsage=false
from http import HTTPStatus
from urllib.parse import urlencode

import pytest
from bs4 import BeautifulSoup
from flask import session
from flask.testing import FlaskClient
from requests_mock import Mocker, adapter

from mixtapestudy.config import SPOTIFY_BASE_URL
from test.conftest import FAKE_ACCESS_TOKEN, FAKE_USER_ID

# TODO: Write tests to handle edge cases and errors
# TODO: Test clicking all the buttons


@pytest.fixture
def mock_search_request(requests_mock: Mocker) -> adapter._Matcher:
    params = urlencode({"q": "test-term", "type": "track", "limit": 8})
    return requests_mock.get(
        f"{SPOTIFY_BASE_URL}/search?{params}",
        request_headers={"authorization": f"Bearer {FAKE_ACCESS_TOKEN}"},
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


def test_load_empty_search_page(client: FlaskClient) -> None:
    with client.session_transaction() as tsession:
        tsession["id"] = FAKE_USER_ID
        tsession["display_name"] = "Test Name"

    search_page_response = client.get("/search")
    assert search_page_response.status_code == HTTPStatus.OK

    soup = BeautifulSoup(search_page_response.text, features="html.parser")
    headings = soup.find_all("h2")
    assert [h.string for h in headings] == ["Selected Songs", "Search for Songs"]

    search_result_table = soup.find("table", {"id": "search-results"})
    search_result_rows = search_result_table.find_all("tr")
    assert len(search_result_rows) == 1, search_result_rows

    # Couldn't think of a better place for this
    assert soup.find(id="display-name").string == "Test Name"

    generate_playlist_button = soup.find(id="generate-playlist")
    assert generate_playlist_button
    assert "disabled" in generate_playlist_button.attrs


def test_load_search_results(client: FlaskClient, mock_search_request: None) -> None:  # noqa: ARG001
    search_page_response = client.get(
        f'/search?{urlencode({"search_term": "test-term"})}'
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

    select_song_form_inputs = first_row.find_all("input")
    add_button = select_song_form_inputs[-1]
    assert "disabled" not in add_button.attrs


def test_load_search_with_selected_songs(
    client: FlaskClient,
    mock_search_request: None,  # noqa: ARG001
) -> None:
    # TODO: break these assertions up into multiple tests
    with client.session_transaction() as tsession:
        tsession["selected_songs"] = [
            {
                "uri": f"spotify:track:test-song-id-{i}",
                "id": f"test-song-id-{i}",
                "name": f"test-song-name-{i}",
                "artist": f"test-song-artist-{i}",
                "artist_raw": f'["test-song-artist-{i}"]',
            }
            for i in range(3)
        ]

    search_page_response = client.get(
        f'/search?{urlencode({"search_term": "test-term"})}'
    )

    assert search_page_response.status_code == HTTPStatus.OK

    soup = BeautifulSoup(search_page_response.text, features="html.parser")

    selected_songs_table = soup.find("table", {"id": "selected-songs"})
    selected_songs_rows = selected_songs_table.find_all("tr")
    selected_song_limit = 3
    assert len(selected_songs_rows) == selected_song_limit, selected_songs_rows

    first_row = selected_songs_rows[0]  # [0] is the header
    first_row_cells = first_row.find_all("td")
    assert [c.string.strip() if c.string else None for c in first_row_cells] == [
        "1",
        "test-song-name-0 (test-song-artist-0)",
        None,
    ]

    last_row = selected_songs_rows[-1]
    last_row_cells = last_row.find_all("td")
    assert [c.string.strip() if c.string else None for c in last_row_cells] == [
        "3",
        "test-song-name-2 (test-song-artist-2)",
        None,
    ]

    generate_playlist_button = soup.find(id="generate-playlist")
    assert generate_playlist_button
    assert "disabled" not in generate_playlist_button.attrs

    search_result_table = soup.find("table", {"id": "search-results"})
    search_result_rows = search_result_table.find_all("tr")

    first_search_result_row = search_result_rows[1]
    select_song_form_inputs = first_search_result_row.find_all("input")
    add_button = select_song_form_inputs[-1]
    assert "disabled" in add_button.attrs


def test_select_song(client: FlaskClient) -> None:
    with client:
        search_page_response = client.post(
            "/search/select",
            data={
                "uri": "spotify:track:test-song-id",
                "id": "test-song-id",
                "name": "test-song-name",
                "artist": "test-song-artist",
                "artist_raw": '["test-song-artist"]',
            },
        )
        assert search_page_response.status_code == HTTPStatus.FOUND
        assert session["selected_songs"] == [
            {
                "uri": "spotify:track:test-song-id",
                "id": "test-song-id",
                "name": "test-song-name",
                "artist": "test-song-artist",
                "artist_raw": '["test-song-artist"]',
            },
            {"id": None},
            {"id": None},
        ]


def test_select_song_in_middle(client: FlaskClient) -> None:
    with client.session_transaction() as tsession:
        tsession["selected_songs"] = [
            {
                "uri": f"spotify:track:test-song-id-{i}",
                "id": f"test-song-id-{i}",
                "name": f"test-song-name-{i}",
                "artist": f"test-song-artist-{i}",
                "artist_raw": f'["test-song-artist-{i}"]',
            }
            for i in range(3)
        ]
        tsession["selected_songs"][1] = {"id": None}

    with client:
        search_page_response = client.post(
            "/search/select",
            data={
                "uri": "spotify:track:test-song-id",
                "id": "test-song-id",
                "name": "test-song-name",
                "artist": "test-song-artist",
                "artist_raw": '["test-song-artist"]',
            },
        )
        assert search_page_response.status_code == HTTPStatus.FOUND
        assert session["selected_songs"][1] == {
            "uri": "spotify:track:test-song-id",
            "id": "test-song-id",
            "name": "test-song-name",
            "artist": "test-song-artist",
            "artist_raw": '["test-song-artist"]',
        }


def test_remove_song(client: FlaskClient) -> None:
    with client.session_transaction() as tsession:
        tsession["selected_songs"] = [
            {
                "uri": "spotify:track:test-song-id",
                "id": f"test-song-id-{i}",
                "name": f"test-song-name-{i}",
                "artist": f"test-song-artist-{i}",
                "artist_raw": f'["test-song-artist-{i}"]',
            }
            for i in range(3)
        ]

    with client:
        remove_response = client.post("/search/remove", data={"index": "2"})
        assert remove_response.status_code == HTTPStatus.FOUND
        assert session["selected_songs"][1] == {"id": None}


def test_generate_playlist_button_disabled_until_three_songs_selected(
    client: FlaskClient,
) -> None:
    with client.session_transaction() as tsession:
        tsession["selected_songs"] = [
            {
                "uri": f"spotify:track:test-song-id-{i}",
                "id": f"test-song-id-{i}",
                "name": f"test-song-name-{i}",
                "artist": f"test-song-artist-{i}",
                "artist_raw": f'["test-song-artist-{i}"]',
            }
            for i in range(3)
        ]
        tsession["selected_songs"][2] = {"id": None}

    search_page_response = client.get("/search")
    assert search_page_response.status_code == HTTPStatus.OK

    soup = BeautifulSoup(search_page_response.text, features="html.parser")
    generate_playlist_button = soup.find(id="generate-playlist")
    assert "disabled" in generate_playlist_button.attrs
