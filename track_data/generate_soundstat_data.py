import csv
import os
import sys
from dataclasses import astuple, dataclass, fields
from http.client import NOT_FOUND
from pathlib import Path
from sqlite3 import connect

import requests
from loguru import logger

from .logsetup import setup_logger

setup_logger(logger)


class RequiredEnvironmentVariableError(Exception):
    def __init__(self, variable: str) -> None:
        self.message = f"Required environment variable '{variable}' not set"
        super().__init__(self.message)


class InvalidCsvFileError(Exception):
    def __init__(self) -> None:
        super().__init__("Invalid csv file provided, first column is not 'spotify_id'")


@dataclass
class TrackData:
    id: str
    name: str
    artists: str
    genre: str
    popularity: int
    tempo: float
    key: int
    mode: int
    key_confidence: float
    energy: float
    danceability: float
    valence: float
    instrumentalness: float
    acousticness: float
    loudness: float
    segments_count: int
    segments_average_duration: float
    beats_count: float
    beats_regularity: float


sqlite_type_map = {
    str: "TEXT",
    int: "INTEGER",
    float: "NUMERIC",
}

api_key = os.environ.get("SOUNDSTAT_API_KEY")
if not api_key:
    raise RequiredEnvironmentVariableError("SOUNDSTAT_API_KEY")

auth_header = {
    "x-api-key": api_key,
    "user-agent": "python/requests (xfyioa+soundstat@gmail.com)",
}

csv_file = sys.argv[1]
if not csv_file:
    raise InvalidCsvFileError

soundstat_cache = connect("../soundstat_cache.db")
table_field_list = [
    f"{field.name} {sqlite_type_map[field.type]}" for field in fields(TrackData)
]
table_field_name_list = [field.name for field in fields(TrackData)]
table_field_placeholder_list = ["?" for _ in fields(TrackData)]
csv_headers = ["isrc", "end_time", "played_ms", *table_field_name_list]

cursor = soundstat_cache.cursor()
cursor.execute(f"CREATE TABLE IF NOT EXISTS track ({', '.join(table_field_list)})")
soundstat_cache.commit()

INSERT_STATEMENT = (
    f"INSERT INTO track "  # noqa: S608
    f"({', '.join(table_field_name_list)}) "
    f"VALUES "
    f"({', '.join(table_field_placeholder_list)})"
)

csv_in_path = Path(csv_file)
csv_out_path = Path(f"{str(csv_in_path).replace('.csv', '_soundstat.csv')}")
logger.info("Reading {} and Writing {}", csv_in_path, csv_out_path)

requests_session = requests.Session()

with csv_in_path.open() as csv_in, csv_out_path.open("w") as csv_out:
    reader = csv.DictReader(csv_in)
    writer = csv.writer(csv_out, dialect="unix")

    writer.writerow(csv_headers)

    for row in reader:
        spotify_id = row["spotify_id"]
        isrc = row["isrc"]
        end_time = row["end_time"]
        played_ms = row["played_ms"]

        cache_found = cursor.execute(
            "SELECT * FROM track WHERE id = ?", (spotify_id,)
        ).fetchone()

        if cache_found:
            logger.info("Track found in the cache: {}", spotify_id)
            track_data = TrackData(*cache_found)
        else:
            soundstat_response = requests_session.get(
                f"https://soundstat.info/api/v1/track/{spotify_id}",
                headers=auth_header,
                timeout=30,
            )
            if soundstat_response.status_code == NOT_FOUND:
                logger.warning(
                    "Track not available yet, try again in a few minutes: {} | {}",
                    spotify_id,
                    soundstat_response.text,
                )
                writer.writerow([isrc, end_time, played_ms, spotify_id])
                continue
            # 404 is the only acceptable non-success code
            soundstat_response.raise_for_status()
            logger.info("Track found on soundstat: {}", spotify_id)

            json_data = soundstat_response.json()
            track_data = TrackData(
                id=json_data["id"],
                name=json_data["name"],
                artists=", ".join(json_data["artists"]),
                genre=json_data["genre"],
                popularity=json_data["popularity"],
                tempo=json_data["features"]["tempo"],
                key=json_data["features"]["key"],
                mode=json_data["features"]["mode"],
                key_confidence=json_data["features"]["key_confidence"],
                energy=json_data["features"]["energy"],
                danceability=json_data["features"]["danceability"],
                valence=json_data["features"]["valence"],
                instrumentalness=json_data["features"]["instrumentalness"],
                acousticness=json_data["features"]["acousticness"],
                loudness=json_data["features"]["loudness"],
                segments_count=json_data["features"]["segments"]["count"],
                segments_average_duration=json_data["features"]["segments"][
                    "average_duration"
                ],
                beats_count=json_data["features"]["beats"]["count"],
                beats_regularity=json_data["features"]["beats"]["regularity"],
            )

            # Relies on Python 3.7+ dict order reliability
            cursor.execute(INSERT_STATEMENT, astuple(track_data))

            soundstat_cache.commit()

        writer.writerow([isrc, end_time, played_ms, *astuple(track_data)])
