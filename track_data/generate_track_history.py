import csv
import inspect
import json
import logging
import os
from sqlite3 import Connection
import sqlite3
import sys
from dataclasses import astuple, dataclass, fields
from pathlib import Path
from typing import TextIO

import requests
from loguru import logger
from requests.auth import HTTPBasicAuth

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
class TrackFeatures:
    spotify_id: str
    isrc: str
    tempo: int
    time_signature: str
    loudness: float
    key: str
    mode: str
    valence: float
    danceability: float
    energe: float
    instrumentalness: float
    acousticness: float


def _get_spotify_token(config: Config) -> str:
    logger.info("Getting Spotify auth token")
    response = requests.post(
        "https://accounts.spotify.com/api/token",
        auth=HTTPBasicAuth(config.spotify_client_id, config.spotify_client_secret),
        data={"grant_type": "client_credentials"},
    )
    response.raise_for_status()
    return response.json()["access_token"]


def _get_track_id(token: str, track: SpotifyTrack) -> str:
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
    logger.debug("  response_json: {}", response_json)

    return response_json["tracks"]["items"][0]["id"]


def _get_track_features(track_id: str) -> TrackFeatures:
    logger.debug("  fetching track features for: {}", track_id)
    return TrackFeatures(
        spotify_id=track_id,
        isrc="temp",
        tempo=-1,
        time_signature="temp",
        loudness=-1.1,
        key="temp",
        mode="temp",
        valence=-1.1,
        danceability=-1.1,
        energe=-1.1,
        instrumentalness=-1.1,
        acousticness=-1.1,
    )


def create_cache_tables(connection: Connection) -> None:
    cursor = connection.cursor()
    cursor.execute(
        "CREATE TABLE track ( "
        "spotify_id TEXT PRIMARY KEY, "
        "artist TEXT, "
        "name TEXT"
        ");"
    )
    cursor.execute("CREATE UNIQUE INDEX name_and_artist ON track (artist, name)")
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
    config: Config, tracks: list[SpotifyTrack], cache_connection: Connection
) -> list[TrackFeatures]:
    track_features = []
    spotify_access_token = None
    cursor = cache_connection.cursor()
    for track in tracks:
        cached_track = cursor.execute(
            "SELECT spotify_id FROM track WHERE artist=? AND name=?",
            (track.artist_name, track.track_name),
        ).fetchone()
        if cached_track:
            track_id = cached_track[0]
        else:
            if not spotify_access_token:
                spotify_access_token = _get_spotify_token(config)
            track_id = _get_track_id(spotify_access_token, track)
        features = _get_track_features(track_id)
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
    try:
        with Path(filepath).open("r") as json_input:
            tracks_loaded = load_history(json_input)

        tracks_features = get_features(config, tracks_loaded, cache_connection)
        write_filepath = filepath.replace(".json", ".csv")
        convert_to_csv(tracks_features, write_filepath)
    finally:
        cache_connection.close()


if __name__ == "__main__":
    main(sys.argv[1])
