import csv
import inspect
import json
import logging
import os
import sqlite3
import sys
from dataclasses import astuple, dataclass, fields
from pathlib import Path
from sqlite3 import Connection, Cursor, Row
from typing import Any, TextIO

import requests
from loguru import logger
from requests.auth import HTTPBasicAuth

# TODO: Fix tests

# Temporary doc/notes (for future reference)
# 1. Local feature extraction: https://essentia.upf.edu/models.html
# 2. Open source feature database (deprecated): https://acousticbrainz.org/
# 3. Drop-in Spotify Proxy (maybe): https://soundlens.pro/api/docs#/operations/api_spotify_replacement_get_audio_features
#    a. Unfortunately it appears to timeout trying to fetch songs
# 4. Song popularity stats: https://songstats.com/for/developers
# 5. Additional links to Kaggle datasets in track_data/README.md


class InterceptHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        # Get corresponding Loguru level if it exists.
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        # Find caller from where originated the logged message.
        frame, depth = inspect.currentframe(), 0
        while frame and (depth == 0 or frame.f_code.co_filename == logging.__file__):
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(
            level, record.getMessage()
        )


logger.remove()
logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)
logger.add(sys.stdout, colorize=True)
requests_logger = logging.getLogger("requests.packages.urllib3")
requests_logger.setLevel(logging.DEBUG)
requests_logger.propagate = True


@dataclass
class Config:
    spotify_client_secret: str
    spotify_client_id: str


@dataclass
class SpotifyTrack:
    end_time: str
    artist_name: str
    track_name: str
    ms_played: int


@dataclass
class SpotifyIds:
    spotify_id: str
    isrc: str


@dataclass
class TrackFeatures:
    spotify_id: str
    isrc: str
    track_name: str
    artist: str
    year: int
    duration_ms: int
    played_ms: int
    end_time: str
    tempo: float
    explicit: bool
    time_signature: int
    loudness: float
    key: str
    mode: str
    speechiness: float
    valence: float
    danceability: float
    energy: float
    liveness: float
    instrumentalness: float
    acousticness: float
    popularity: float
    genre: str
    beats_per_minute: int


class NoTrackFoundError(Exception): ...


def _get_spotify_token(config: Config) -> str:
    logger.info("Getting Spotify auth token")
    response = requests.post(
        "https://accounts.spotify.com/api/token",
        auth=HTTPBasicAuth(config.spotify_client_id, config.spotify_client_secret),
        data={"grant_type": "client_credentials"},
    )
    response.raise_for_status()
    return response.json()["access_token"]


def _get_track_ids(token: str, track: SpotifyTrack) -> SpotifyIds:
    logger.debug("  fetching track ID for: {}", track)
    response = requests.get(
        "https://api.spotify.com/v1/search",
        headers={"Authorization": f"Bearer {token}"},
        params={
            "q": f"artist:{track.artist_name} track:{track.track_name}",
            "type": "track",
            "limit": 1,
        },
    )
    response.raise_for_status()
    response_json = response.json()
    # logger.debug("  response: {}", response.text)

    if response_json and response_json["tracks"] and response_json["tracks"]["items"]:
        first_result = response_json["tracks"]["items"][0]
    else:
        logger.warning("No tracks returned for {}: {}", track, response_json)
        raise NoTrackFoundError
    return SpotifyIds(
        spotify_id=first_result["id"],
        isrc=first_result["external_ids"]["isrc"],
    )


def _get_track_features(
    track_id: str,
    isrc: str,
    spotify_track: SpotifyTrack,
    features_connection: Connection,
) -> TrackFeatures:
    logger.debug("  fetching track features for: {}", track_id)
    cursor = features_connection.cursor()
    cursor.row_factory = _dict_factory
    related_rows = cursor.execute(
        "SELECT * FROM features WHERE spotify_id=? OR isrc=?", (track_id, isrc)
    ).fetchall()

    consolidated_dict = {}
    for row in related_rows:
        for k, v in row.items():
            if v:
                consolidated_dict[k] = v

    return TrackFeatures(
        spotify_id=track_id,
        isrc=isrc,
        track_name=spotify_track.track_name,
        artist=spotify_track.artist_name,
        year=consolidated_dict.get("year"),
        duration_ms=consolidated_dict.get("duration_ms"),
        played_ms=spotify_track.ms_played,
        end_time=spotify_track.end_time,
        tempo=consolidated_dict.get("tempo"),
        explicit=consolidated_dict.get("explicit"),
        time_signature=consolidated_dict.get("time_signature"),
        loudness=consolidated_dict.get("loudness"),
        key=consolidated_dict.get("key"),
        mode=consolidated_dict.get("mode"),
        speechiness=consolidated_dict.get("speechiness"),
        valence=consolidated_dict.get("valence"),
        danceability=consolidated_dict.get("danceability"),
        energy=consolidated_dict.get("energy"),
        liveness=consolidated_dict.get("liveness"),
        instrumentalness=consolidated_dict.get("instrumentalness"),
        acousticness=consolidated_dict.get("acousticness"),
        popularity=consolidated_dict.get("popularity"),
        genre=consolidated_dict.get("genre"),
        beats_per_minute=consolidated_dict.get("beats_per_minute"),
    )


def _dict_factory(cursor: Cursor, row: Row) -> dict[str, Any]:
    # From: https://docs.python.org/3.11/library/sqlite3.html
    return dict(zip([column[0] for column in cursor.description], row))


def create_cache_tables(connection: Connection) -> None:
    cursor = connection.cursor()
    cursor.execute(
        "CREATE TABLE IF NOT EXISTS track ( "
        "spotify_id TEXT, "
        "isrc TEXT, "
        "artist TEXT, "
        "name TEXT"
        ");"
    )
    cursor.execute("CREATE INDEX IF NOT EXISTS name_and_artist ON track (artist, name)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_spotify_id ON track(spotify_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_isrc ON track(isrc)")
    connection.commit()


def load_history(json_input: TextIO) -> list[SpotifyTrack]:
    raw_input = json.load(json_input)
    return [
        SpotifyTrack(
            end_time=d["endTime"],
            artist_name=d["artistName"],
            track_name=d["trackName"],
            ms_played=d["msPlayed"],
        )
        for d in raw_input
    ]


def get_features(
    config: Config,
    tracks: list[SpotifyTrack],
    cache_connection: Connection,
    features_connection: Connection,
) -> list[TrackFeatures]:
    track_features = []
    spotify_access_token = None
    cursor = cache_connection.cursor()
    for track in tracks:
        cached_track = cursor.execute(
            "SELECT spotify_id, isrc FROM track WHERE artist=? AND name=?",
            (track.artist_name, track.track_name),
        ).fetchone()
        if cached_track:
            track_id = cached_track[0]
            isrc = cached_track[1]
        else:
            if not spotify_access_token:
                spotify_access_token = _get_spotify_token(config)
            try:
                track_ids = _get_track_ids(spotify_access_token, track)
            except NoTrackFoundError:
                continue
            track_id = track_ids.spotify_id
            isrc = track_ids.isrc
            cursor.execute(
                "INSERT INTO track (spotify_id, isrc, artist, name) VALUES (?, ?, ?, ?)",
                (track_id, isrc, track.artist_name, track.track_name),
            )
            cache_connection.commit()
        features = _get_track_features(track_id, isrc, track, features_connection)
        track_features.append(features)
    return track_features


def convert_to_csv(tracks: list[TrackFeatures], filepath: str) -> None:
    with Path(filepath).open("w") as csv_out:
        headers = [f.name for f in fields(TrackFeatures)]
        writer = csv.writer(csv_out, dialect="unix")
        writer.writerow(headers)
        for track in tracks:
            track_dict = astuple(track)
            writer.writerow(track_dict)


def main(filepath: str) -> None:
    config = Config(
        spotify_client_secret=os.getenv("SPOTIFY_CLIENT_SECRET", "invalid"),
        spotify_client_id=os.getenv("SPOTIFY_CLIENT_ID", "invalid"),
    )
    if "invalid" in (config.spotify_client_secret, config.spotify_client_id):
        logger.error("Invalid environment variable set: {}", config)
        sys.exit(1)

    cache_connection = sqlite3.connect("cache.db")
    features_connection = sqlite3.connect("features.db")
    create_cache_tables(cache_connection)
    try:
        with Path(filepath).open("r") as json_input:
            tracks_loaded = load_history(json_input)

        tracks_features = get_features(
            config, tracks_loaded, cache_connection, features_connection
        )
        write_filepath = filepath.replace(".json", ".csv")
        convert_to_csv(tracks_features, write_filepath)
    finally:
        cache_connection.close()


if __name__ == "__main__":
    main(sys.argv[1])
