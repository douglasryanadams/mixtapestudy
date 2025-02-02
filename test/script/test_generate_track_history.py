import csv
import sqlite3
from base64 import b64encode
from collections.abc import Iterator
from dataclasses import asdict
from pathlib import Path
from sqlite3 import Connection
from urllib.parse import urlencode

import pytest
from requests_mock import Mocker, adapter

from track_data.generate_feature_sources import create_features_table
from track_data.generate_track_history import (
    Config,
    SpotifyTrack,
    TrackFeatures,
    convert_to_csv,
    create_cache_tables,
    get_features,
    load_history,
)

FAKE_ACCESS_TOKEN = "fake-access-token"  # noqa: S105
PATH_CACHE = Path("test_cache.db")
PATH_FEATURES = Path("test_features.db")
PATH_ALL_DATA = Path("test/data/music_history_all.json")
PATH_PARTIAL_DATA = Path("test/data/music_history_missing_data.json")
PATH_REALISTIC_DATA = Path("test/data/music_history_realistic.json")
PATH_SHORT_DATA = Path("test/data/music_history_short.json")
ALL_PATHS = (PATH_ALL_DATA, PATH_PARTIAL_DATA, PATH_REALISTIC_DATA, PATH_SHORT_DATA)


@pytest.fixture
def config() -> Config:
    return Config("fake-secret", "fake-id")


@pytest.fixture
def short_history_data() -> list[SpotifyTrack]:
    with PATH_SHORT_DATA.open("r") as data_file:
        return load_history(data_file)


@pytest.fixture
def cache_connection() -> Iterator[Connection]:
    connection = sqlite3.connect(PATH_CACHE)
    create_cache_tables(connection)
    yield connection
    connection.close()
    PATH_CACHE.unlink()


@pytest.fixture
def features_connection() -> Iterator[Connection]:
    connection = sqlite3.connect(PATH_FEATURES)
    create_features_table(connection)
    yield connection
    connection.close()
    PATH_FEATURES.unlink()


@pytest.fixture
def populated_cache(
    cache_connection: Connection, short_history_data: list[SpotifyTrack]
) -> Connection:
    data = [
        (f"track-id-{i}", "isrc-{i}", track.artist_name, track.track_name)
        for i, track in enumerate(short_history_data)
    ]
    cursor = cache_connection.cursor()
    cursor.executemany("INSERT INTO track VALUES (?, ?, ?, ?)", data)
    cache_connection.commit()
    return cache_connection


@pytest.fixture
def populated_features(
    features_connection: Connection, short_history_data: list[SpotifyTrack]
) -> Connection:
    data = [
        (
            1,  # acousticness
            1,  # beats per minute
            1,  # danceability
            1000,  # duration in milliseconds
            1,  # energy
            1,  # explicit
            "genre",
            1,  # instrumentalness
            f"isrc-{i}",  # ISRC
            1,  # key
            1,  # liveness
            1,  # loudness
            1,  # mode
            1,  # popularity
            f"artist-name-{i}",  # primary artist
            1,  # speechiness
            f"track-id-{i}",  # spotify_id
            10,  # tempo
            1,  # time_signature
            f"track-name-{i}",  # track name
            1,  # valence
            1986,  # year
        )
        for i, track in enumerate(short_history_data)
    ]
    cursor = features_connection.cursor()
    cursor.executemany(
        "INSERT INTO features ("  # noqa: S608
        "acousticness, "
        "beats_per_minute, "
        "danceability, "
        "duration_ms, "
        "energy, "
        "explicit, "
        "genre, "
        "instrumentalness, "
        "isrc, "
        "key, "
        "liveness, "
        "loudness, "
        "mode, "
        "popularity, "
        "artist, "
        "speechiness, "
        "spotify_id, "
        "tempo, "
        "time_signature, "
        "track_name, "
        "valence, "
        "year"
        f") VALUES ({', '.join(['?' for _ in range(22)])})",
        data,
    )
    features_connection.commit()
    return features_connection


@pytest.fixture
def fake_spotify_token(config: Config, requests_mock: Mocker) -> adapter._Matcher:
    encoded_fake_auth = b64encode(
        f"{config.spotify_client_id}:{config.spotify_client_secret}".encode()
    ).decode("utf8")
    return requests_mock.post(
        "https://accounts.spotify.com/api/token",
        request_headers={
            "content-type": "application/x-www-form-urlencoded",
            "Authorization": f"Basic {encoded_fake_auth}",
        },
        json={"access_token": FAKE_ACCESS_TOKEN},
    )


@pytest.fixture
def fake_search_history_short(
    short_history_data: list[SpotifyTrack], requests_mock: Mocker
) -> list[adapter._Matcher]:
    mocked_requests = []
    for track_id_counter, track in enumerate(short_history_data):
        params = urlencode(
            {
                "q": f"artist:{track.artist_name} track:{track.track_name}",
                "type": "track",
                "limit": 1,
            }
        )
        mocked_requests.append(
            requests_mock.get(
                f"https://api.spotify.com/v1/search?{params}",
                request_headers={"Authorization": f"Bearer {FAKE_ACCESS_TOKEN}"},
                json={
                    "tracks": {
                        "items": [
                            {
                                "id": f"track-id-{track_id_counter}",
                                "external_ids": {"isrc": f"isrc-{track_id_counter}"},
                            }
                        ]
                    }
                },
            )
        )
    return mocked_requests


@pytest.fixture
def csv_location() -> Iterator[str]:
    filename = "tmp_test.csv"
    yield filename
    Path(filename).unlink()


@pytest.fixture
def fake_csv_tracks() -> list[TrackFeatures]:
    return [
        TrackFeatures(
            spotify_id=f"track-id-{i}",
            track_name=f"track-{i}",
            artist=f"artist-{i}",
            isrc=f"isrc={i}",
            year=-1,
            duration_ms=-1,
            played_ms=-1,
            end_time="test",
            tempo=-1,
            explicit=False,
            time_signature=-1,
            loudness=-0.1,
            key="test",
            mode="test",
            speechiness=-0.1,
            valence=-0.1,
            danceability=-0.1,
            energy=-0.1,
            liveness=-0.1,
            instrumentalness=-0.1,
            acousticness=-0.1,
            popularity=-0.1,
            genre="test",
            beats_per_minute=-1,
        )
        for i in range(10)
    ]


def test_load_history(short_history_data: list[SpotifyTrack]) -> None:
    assert short_history_data == [
        SpotifyTrack(
            end_time="2023-04-09 03:55",
            artist_name="John Mayer",
            track_name="Heartbreak Warfare",
            ms_played=265550,
        ),
        SpotifyTrack(
            end_time="2023-04-09 04:00",
            artist_name="John Mayer",
            track_name="All We Ever Do Is Say Goodbye",
            ms_played=271011,
        ),
        SpotifyTrack(
            end_time="2023-04-09 04:01",
            artist_name="John Mayer",
            track_name="Half of My Heart",
            ms_played=90674,
        ),
    ]


@pytest.mark.parametrize("track_path", ALL_PATHS)
def test_load_history_any_size(track_path: Path) -> None:
    with track_path.open("r") as data_file:
        load_history(data_file)


def test_get_features(  # noqa: PLR0913
    config: Config,
    short_history_data: list[SpotifyTrack],
    fake_spotify_token: adapter._Matcher,
    fake_search_history_short: list[adapter._Matcher],
    cache_connection: Connection,
    populated_features: Connection,
) -> None:
    features = get_features(
        config, short_history_data, cache_connection, populated_features
    )
    track_count = 3
    assert len(features) == track_count
    for i, feature in enumerate(features):
        assert feature.spotify_id == f"track-id-{i}"
        assert feature.isrc == f"isrc-{i}"
        for v in asdict(feature).values():
            assert v

    assert fake_spotify_token.called
    for history in fake_search_history_short:
        assert history.called


def test_get_features_cached(  # noqa: PLR0913
    config: Config,
    short_history_data: list[SpotifyTrack],
    fake_spotify_token: adapter._Matcher,
    fake_search_history_short: list[adapter._Matcher],
    populated_cache: Connection,
    populated_features: Connection,
) -> None:
    features = get_features(
        config, short_history_data, populated_cache, populated_features
    )
    track_count = 3
    assert len(features) == track_count
    for i in range(track_count):
        assert features[i].spotify_id == f"track-id-{i}"
    assert not fake_spotify_token.called
    for history in fake_search_history_short:
        assert not history.called


def test_convert_to_csv(
    csv_location: str, fake_csv_tracks: list[TrackFeatures]
) -> None:
    convert_to_csv(fake_csv_tracks, csv_location)
    with Path(csv_location).open() as csv_in:
        reader = csv.reader(csv_in, dialect="unix")
        rows = list(reader)
    row_count_with_header = 11

    assert len(rows) == row_count_with_header
    rows.pop(0)
    for i, row in enumerate(rows):
        assert row[0] == f"track-id-{i}"
