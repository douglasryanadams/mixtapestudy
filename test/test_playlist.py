import json
from http import HTTPStatus
from unittest.mock import patch
from urllib.parse import urlencode

import pytest
from bs4 import BeautifulSoup
from flask.testing import FlaskClient
from requests_mock import Mocker, adapter

from mixtapestudy.config import SPOTIFY_BASE_URL, RecommendationService
from test.conftest import FAKE_ACCESS_TOKEN, FAKE_LISTENBRAINZ_API_KEY

# TODO: Tests for edge cases


@pytest.fixture
def mock_recommendation_request(requests_mock: Mocker) -> adapter._Matcher:
    params = urlencode(
        {"seed_tracks": ",".join([f"selected-song-{i}" for i in range(3)]), "limit": 72}
    )
    return requests_mock.get(
        f"{SPOTIFY_BASE_URL}/recommendations?{params}",
        request_headers={"Authorization": f"Bearer {FAKE_ACCESS_TOKEN}"},
        json={
            # This is a dramatically simplified version of this response
            # For full example see:
            #   https://developer.spotify.com/documentation/web-api/reference/get-recommendations
            "tracks": [
                {
                    "uri": f"spotify:song-{i}",
                    "id": f"song-{i}",
                    "name": f"name-{i}",
                    "artists": [{"name": f"artist-{i}-{k}"} for k in range(3)],
                }
                for i in range(72)
            ]
        },
    )


@pytest.fixture
def mock_listenbrainz_radio_request(requests_mock: Mocker) -> adapter._Matcher:
    params = urlencode(
        {
            "mode": "easy",
            "prompt": " ".join([f"artist:(selected-artist-{i})" for i in range(3)]),
        }
    )
    return requests_mock.get(
        url=f"https://api.listenbrainz.org/1/explore/lb-radio?{params}",
        request_headers={"Authorization": f"Bearer {FAKE_LISTENBRAINZ_API_KEY}"},
        json={
            # This is a dramatically simplified version of this response
            # For full example see:
            #   curl 'https://api.listenbrainz.org/1/explore/lb-radio?prompt=artist%3A(noah%20gundersen)&mode=easy' | jq  # noqa: E501
            "payload": {
                "jspf": {
                    "playlist": {
                        "track": [
                            {
                                "title": f"name-{i}",
                                "identifier": [
                                    f"https://musicbrainz.org/recording/fake-uuid-{i}"
                                ],
                                "creator": f"artist-{i}",
                            }
                            for i in range(32)
                        ]
                    }
                }
            }
        },
    )


@pytest.fixture
def mock_create_playlist(requests_mock: Mocker) -> adapter._Matcher:
    return requests_mock.post(
        f"{SPOTIFY_BASE_URL}/users/fake-spotify-id/playlists",
        request_headers={"Authorization": f"Bearer {FAKE_ACCESS_TOKEN}"},
        json={"id": "fake-playlist-id"},
    )


@pytest.fixture
def mock_add_songs_to_playlist(requests_mock: Mocker) -> adapter._Matcher:
    return requests_mock.post(
        f"{SPOTIFY_BASE_URL}/playlists/fake-playlist-id/tracks",
        request_headers={"Authorization": f"Bearer {FAKE_ACCESS_TOKEN}"},
    )


def test_load_without_session(client_without_session: FlaskClient) -> None:
    r = client_without_session.post("/playlist/preview")
    assert r.status_code == HTTPStatus.FOUND
    assert r.location == "/"


def test_load_page_recommendation_service_spotify(
    client: FlaskClient,
    mock_recommendation_request: adapter._Matcher,
) -> None:
    with client.session_transaction() as tsession:
        tsession["selected_songs"] = [
            {
                "uri": f"spotify:track:selected-song-{i}",
                "id": f"selected-song-{i}",
                "name": f"selected-name-{i}",
                "artist": f"selected-artist-{i}",
                "artist_raw": f'["selected-artist-{i}"]',
            }
            for i in range(3)
        ]

    playlist_page_response = client.post("/playlist/preview")

    assert mock_recommendation_request.called

    soup = BeautifulSoup(playlist_page_response.text, "html.parser")
    table_rows = soup.find_all("tr")
    number_of_songs = 75
    assert len(table_rows) == number_of_songs + 1  # Extra row for header

    first_row = table_rows[1].find_all("td")
    assert [c.string for c in first_row] == [
        "selected-name-0",
        "selected-artist-0",
    ]

    fourth_row = table_rows[4].find_all("td")
    assert [c.string for c in fourth_row] == [
        "name-0",
        "artist-0-0, artist-0-1, artist-0-2",
    ]

    last_row = table_rows[-1].find_all("td")
    assert [c.string for c in last_row] == [
        "name-71",
        "artist-71-0, artist-71-1, artist-71-2",
    ]

    assert not soup.find(id="success-header")
    assert not soup.find(id="error-header")


def test_load_page_recommendation_service_listenbrainz(
    client: FlaskClient,
    mock_listenbrainz_radio_request: adapter._Matcher,
) -> None:
    with client.session_transaction() as tsession:
        tsession["selected_songs"] = [
            {
                "uri": f"spotify:track:selected-song-{i}",
                "id": f"selected-song-{i}",
                "name": f"selected-name-{i}",
                "artist": f"selected-artist-{i}",
                "artist_raw": f'["selected-artist-{i}"]',
            }
            for i in range(3)
        ]

    with patch("mixtapestudy.routes.playlist.get_config") as fake_get_config:
        fake_get_config.return_value.recommendation_service = (
            RecommendationService.LISTENBRAINZ
        )
        fake_get_config.return_value.listenbrainz_api_key = FAKE_LISTENBRAINZ_API_KEY
        playlist_page_response = client.post("/playlist/preview")

    assert mock_listenbrainz_radio_request.called

    soup = BeautifulSoup(playlist_page_response.text, "html.parser")
    table_rows = soup.find_all("tr")
    number_of_songs = 35
    assert len(table_rows) == number_of_songs + 1  # Extra row for header

    first_row = table_rows[1].find_all("td")
    assert [c.string for c in first_row] == [
        "selected-name-0",
        "selected-artist-0",
    ]

    fourth_row = table_rows[4].find_all("td")
    assert [c.string for c in fourth_row] == [
        "name-0",
        "artist-0",
    ]

    last_row = table_rows[-1].find_all("td")
    assert [c.string for c in last_row] == [
        "name-31",
        "artist-31",
    ]

    assert not soup.find(id="success-header")
    assert not soup.find(id="error-header")


def test_save_playlist(
    client: FlaskClient,
    mock_create_playlist: adapter._Matcher,
    mock_add_songs_to_playlist: adapter._Matcher,
) -> None:
    payload = [
        {
            "uri": f"spotify:track:song-{i}",
            "id": f"song-{i}",
            "name": f"name-{i}",
            "artist": f"artist-{i}",
        }
        for i in range(75)
    ]
    r = client.post(
        "/playlist/save",
        data={
            "playlist_songs": json.dumps(payload),
            "playlist_name": "Test Playlist",
        },
    )

    assert r.status_code == HTTPStatus.FOUND
    assert r.location == "https://open.spotify.com/playlist/fake-playlist-id"

    assert mock_create_playlist.called
    assert mock_add_songs_to_playlist.called

    assert mock_create_playlist.last_request
    assert mock_create_playlist.last_request.json() == {
        "name": "Test Playlist (2020-01-01 00:00:00)",
        "description": "Generated by mixtapestudy.com",
        "public": True,
        "collaborative": False,
    }

    assert mock_add_songs_to_playlist.last_request
    assert mock_add_songs_to_playlist.last_request.json() == {
        "uris": [song["uri"] for song in payload]
    }
