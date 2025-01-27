import csv
from dataclasses import dataclass
from enum import Enum, StrEnum
import inspect
import logging
import sqlite3
import sys
from pathlib import Path
from zipfile import ZipFile

import requests
from loguru import logger

# Note: This file doesn't have unit tests, it either works or it doesn't
# because the HTTP calls are cached and long running.


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


class CsvFeature(StrEnum):
    ACOUSTICNESS = "acousticness"
    BEATS_PER_MINUTE = "beats_per_minute"
    DANCEABILITY = "danceability"
    DURATION_MS = "duration_ms"
    ENERGY = "energy"
    EXPLICIT = "explicit"
    GENRE = "genre"
    INSTRUMENTALNESS = "instrumentalness"
    ISRC = "isrc"
    KEY = "key"
    LIVENESS = "liveness"
    LOUDNESS = "loudness"
    MODE = "mode"
    POPULARITY = "popularity"
    PRIMARY_ARTIST = "primary_artist"
    SPEECHINESS = "speechiness"
    SPOTIFY_ID = "spotify_id"
    SPOTIFY_URI = "spotify_uri"  # This is special, it needs parsing
    TEMPO = "tempo"
    TIME_SIGNATURE = "time_signature"
    TRACK_NAME = "track_name"
    VALENCE = "valence"
    YEAR = "year"


@dataclass
class Column:
    datatype: type
    new_key: CsvFeature


@dataclass
class Download:
    filenames: list[str]
    column_map: dict[str, Column]


KAGGLE_BASE_URL = "https://www.kaggle.com/api/v1/datasets/download"
DOWNLOAD_DIR = Path("./download/")

# This section of the script is huge, but makes it much easier
# to add new sources of data as they're discovered.
# It also makes it possible for others using this repo to rebuild
# the data cache from these files.
DOWNLOADS: dict[str, Download] = {
    "rodolfofigueroa/spotify-12m-songs": Download(
        filenames=["tracks_features.csv"],
        column_map={
            "acousticness": Column(float, CsvFeature.ACOUSTICNESS),
            "artists": Column(list[str], CsvFeature.PRIMARY_ARTIST),
            "danceability": Column(str, CsvFeature.DANCEABILITY),
            "duration_ms": Column(int, CsvFeature.DURATION_MS),
            "energy": Column(str, CsvFeature.ENERGY),
            "explicit": Column(str, CsvFeature.EXPLICIT),
            "id": Column(str, CsvFeature.SPOTIFY_ID),
            "instrumentalness": Column(float, CsvFeature.INSTRUMENTALNESS),
            "key": Column(str, CsvFeature.KEY),
            "liveness": Column(float, CsvFeature.LIVENESS),
            "loudness": Column(float, CsvFeature.LOUDNESS),
            "mode": Column(str, CsvFeature.MODE),
            "name": Column(str, CsvFeature.TRACK_NAME),
            "speechiness": Column(float, CsvFeature.SPEECHINESS),
            "tempo": Column(int, CsvFeature.TEMPO),
            "time_signature": Column(str, CsvFeature.TIME_SIGNATURE),
            "valence": Column(float, CsvFeature.VALENCE),
            "year": Column(str, CsvFeature.YEAR),
        },
    ),
    # No Spotify IDs but 50k rows
    # "vicsuperman/prediction-of-music-genre": Download(
    #     filenames=["music_genre.csv"],
    #     column_map={
    #         "acousticness": Column(float, CsvFeature.ACOUSTICNESS),
    #         "artist_name": Column(str, CsvFeature.PRIMARY_ARTIST),
    #         "danceability": Column(float, CsvFeature.DANCEABILITY),
    #         "duration_ms": Column(int, CsvFeature.DURATION_MS),
    #         "energy": Column(float, CsvFeature.ENERGY),
    #         "instrumentalness": Column(float, CsvFeature.INSTRUMENTALNESS),
    #         "key": Column(str, CsvFeature.KEY),
    #         "liveness": Column(float, CsvFeature.LIVENESS),
    #         "loudness": Column(float, CsvFeature.LOUDNESS),
    #         "mode": Column(str, CsvFeature.MODE),
    #         "music_genre": Column(str, CsvFeature.GENRE),
    #         "popularity": Column(float, CsvFeature.POPULARITY),
    #         "speechiness": Column(float, CsvFeature.SPEECHINESS),
    #         "tempo": Column(int, CsvFeature.TEMPO),
    #         "track_name": Column(str, CsvFeature.TRACK_NAME),
    #         "valence": Column(float, CsvFeature.VALENCE),
    #     },
    # ),
    "mcfurland/10-m-beatport-tracks-spotify-audio-features": Download(
        # These files are different from the others in that they each have
        # partial data, the order is important in this case because
        # we'll use the cached values from the first file to write the
        # data from the second file in the appropriate rows
        filenames=["sp_track.csv", "audio_features.csv"],
        column_map={
            "acousticness": Column(float, CsvFeature.ACOUSTICNESS),
            "danceability": Column(float, CsvFeature.DANCEABILITY),
            "duration_ms": Column(float, CsvFeature.DURATION_MS),
            "energy": Column(float, CsvFeature.ENERGY),
            "explicit": Column(float, CsvFeature.EXPLICIT),
            "instrumentalness": Column(float, CsvFeature.INSTRUMENTALNESS),
            "isrc": Column(float, CsvFeature.ISRC),
            "key": Column(float, CsvFeature.KEY),
            "liveness": Column(float, CsvFeature.LIVENESS),
            "loudness": Column(float, CsvFeature.LOUDNESS),
            "mode": Column(float, CsvFeature.MODE),
            "speechiness": Column(float, CsvFeature.SPEECHINESS),
            "tempo": Column(float, CsvFeature.TEMPO),
            "time_signature": Column(float, CsvFeature.TIME_SIGNATURE),
            "track_id": Column(float, CsvFeature.SPOTIFY_ID),
            "track_title": Column(float, CsvFeature.TRACK_NAME),
            "valence": Column(float, CsvFeature.VALENCE),
        },
    ),
    "maharshipandya/-spotify-tracks-dataset": Download(
        filenames=["dataset.csv"],
        column_map={
            "acousticness": Column(float, CsvFeature.ACOUSTICNESS),
            "artists": Column(str, CsvFeature.PRIMARY_ARTIST),
            "danceability": Column(float, CsvFeature.DANCEABILITY),
            "duration_ms": Column(int, CsvFeature.DURATION_MS),
            "energy": Column(float, CsvFeature.ENERGY),
            "explicit": Column(bool, CsvFeature.EXPLICIT),
            "instrumentalness": Column(float, CsvFeature.INSTRUMENTALNESS),
            "liveness": Column(float, CsvFeature.LIVENESS),
            "loudness": Column(float, CsvFeature.LOUDNESS),
            "popularity": Column(float, CsvFeature.POPULARITY),
            "speechiness": Column(float, CsvFeature.SPEECHINESS),
            "tempo": Column(int, CsvFeature.TEMPO),
            "track_genre": Column(str, CsvFeature.GENRE),
            "track_id": Column(str, CsvFeature.SPOTIFY_ID),
            "track_name": Column(str, CsvFeature.TRACK_NAME),
            "valence": Column(float, CsvFeature.VALENCE),
        },
    ),
    "solomonameh/spotify-music-dataset": Download(
        filenames=[
            "high_popularity_spotify_data.csv",
            "low_popularity_spotify_data.csv",
        ],
        column_map={
            "acousticness": Column(float, CsvFeature.ACOUSTICNESS),
            "danceability": Column(float, CsvFeature.DANCEABILITY),
            "duration_ms": Column(int, CsvFeature.DURATION_MS),
            "energy": Column(float, CsvFeature.ENERGY),
            "id": Column(str, CsvFeature.SPOTIFY_ID),
            "instrumentalness": Column(float, CsvFeature.INSTRUMENTALNESS),
            "key": Column(int, CsvFeature.KEY),
            "liveness": Column(float, CsvFeature.LIVENESS),
            "loudness": Column(float, CsvFeature.LOUDNESS),
            "mode": Column(int, CsvFeature.MODE),
            "playlist_genre": Column(str, CsvFeature.GENRE),
            "speechiness": Column(float, CsvFeature.SPEECHINESS),
            "tempo": Column(float, CsvFeature.TEMPO),
            "time_signature": Column(int, CsvFeature.TIME_SIGNATURE),
            "track_artist": Column(str, CsvFeature.PRIMARY_ARTIST),
            "track_name": Column(str, CsvFeature.TRACK_NAME),
            "track_popularity": Column(float, CsvFeature.POPULARITY),
            "valence": Column(float, CsvFeature.VALENCE),
        },
    ),
    "joebeachcapital/30000-spotify-songs": Download(
        filenames=["spotify_songs.csv"],
        column_map={
            "acousticness": Column(float, CsvFeature.ACOUSTICNESS),
            "danceability": Column(float, CsvFeature.DANCEABILITY),
            "duration_ms": Column(int, CsvFeature.DURATION_MS),
            "energy": Column(float, CsvFeature.ENERGY),
            "instrumentalness": Column(float, CsvFeature.ENERGY),
            "key": Column(int, CsvFeature.KEY),
            "liveness": Column(float, CsvFeature.LIVENESS),
            "loudness": Column(float, CsvFeature.LOUDNESS),
            "mode": Column(int, CsvFeature.MODE),
            "playlist_genre": Column(str, CsvFeature.GENRE),
            "speechiness": Column(float, CsvFeature.SPEECHINESS),
            "tempo": Column(float, CsvFeature.TEMPO),
            "track_artist": Column(str, CsvFeature.PRIMARY_ARTIST),
            "track_id": Column(str, CsvFeature.SPOTIFY_ID),
            "track_name": Column(str, CsvFeature.TRACK_NAME),
            "track_popularity": Column(int, CsvFeature.POPULARITY),
            "valence": Column(float, CsvFeature.VALENCE),
        },
    ),
    "theoverman/the-spotify-hit-predictor-dataset": Download(
        filenames=[
            "dataset-of-00s.csv",
            "dataset-of-10s.csv",
            "dataset-of-60s.csv",
            "dataset-of-70s.csv",
            "dataset-of-80s.csv",
            "dataset-of-90s.csv",
        ],
        column_map={
            "acousticness": Column(float, CsvFeature.ACOUSTICNESS),
            "artist": Column(str, CsvFeature.PRIMARY_ARTIST),
            "danceability": Column(float, CsvFeature.DANCEABILITY),
            "duration_ms": Column(int, CsvFeature.DURATION_MS),
            "energy": Column(float, CsvFeature.ENERGY),
            "instrumentalness": Column(float, CsvFeature.INSTRUMENTALNESS),
            "key": Column(int, CsvFeature.KEY),
            "liveness": Column(float, CsvFeature.LIVENESS),
            "loudness": Column(float, CsvFeature.LOUDNESS),
            "mode": Column(float, CsvFeature.MODE),
            "speechiness": Column(float, CsvFeature.SPEECHINESS),
            "tempo": Column(float, CsvFeature.TEMPO),
            "time_signature": Column(int, CsvFeature.TIME_SIGNATURE),
            "track": Column(str, CsvFeature.TRACK_NAME),
            "uri": Column(str, CsvFeature.SPOTIFY_URI),
            "valence": Column(float, CsvFeature.VALENCE),
        },
    ),
    "byomokeshsenapati/spotify-song-attributes": Download(
        filenames=["Spotify_Song_Attributes.csv"],
        column_map={
            "acousticness": Column(float, CsvFeature.ACOUSTICNESS),
            "artistName": Column(str, CsvFeature.PRIMARY_ARTIST),
            "danceability": Column(float, CsvFeature.DANCEABILITY),
            "duration_ms": Column(int, CsvFeature.DURATION_MS),
            "energy": Column(float, CsvFeature.ENERGY),
            "genre": Column(str, CsvFeature.GENRE),
            "id": Column(str, CsvFeature.SPOTIFY_ID),
            "instrumentalness": Column(float, CsvFeature.INSTRUMENTALNESS),
            "key": Column(float, CsvFeature.KEY),
            "liveness": Column(float, CsvFeature.LIVENESS),
            "loudness": Column(float, CsvFeature.LOUDNESS),
            "mode": Column(float, CsvFeature.MODE),
            "speechiness": Column(float, CsvFeature.SPEECHINESS),
            "tempo": Column(float, CsvFeature.TEMPO),
            "time_signature": Column(float, CsvFeature.TIME_SIGNATURE),
            "trackName": Column(str, CsvFeature.TRACK_NAME),
            "valence": Column(float, CsvFeature.VALENCE),
        },
    ),
    "gauthamvijayaraj/spotify-tracks-dataset-updated-every-week": Download(
        filenames=["spotify_tracks.csv"],
        column_map={
            "acousticness": Column(float, CsvFeature.ACOUSTICNESS),
            "artist_name": Column(str, CsvFeature.PRIMARY_ARTIST),
            "danceability": Column(float, CsvFeature.DANCEABILITY),
            "duration_ms": Column(int, CsvFeature.DURATION_MS),
            "energy": Column(float, CsvFeature.ENERGY),
            "instrumentalness": Column(float, CsvFeature.INSTRUMENTALNESS),
            "key": Column(float, CsvFeature.KEY),
            "liveness": Column(float, CsvFeature.LIVENESS),
            "loudness": Column(float, CsvFeature.LOUDNESS),
            "mode": Column(float, CsvFeature.MODE),
            "popularity": Column(float, CsvFeature.POPULARITY),
            "speechiness": Column(float, CsvFeature.SPEECHINESS),
            "tempo": Column(float, CsvFeature.TEMPO),
            "time_signature": Column(float, CsvFeature.TIME_SIGNATURE),
            "track_id": Column(float, CsvFeature.SPOTIFY_ID),
            "track_name": Column(float, CsvFeature.TRACK_NAME),
            "valence": Column(float, CsvFeature.VALENCE),
            "year": Column(float, CsvFeature.YEAR),
        },
    ),
}


def _download_kaggle_data(kaggle_path: str, download_path: Path):
    request_path = f"{KAGGLE_BASE_URL}/{kaggle_path}"

    logger.info("Downloading: {}", request_path)
    response = requests.get(request_path, stream=True, timeout=120)
    logger.debug(">> response: {}", response)
    response.raise_for_status()

    content_length = int(response.headers["content-length"])
    logger.debug(">> writing {} byte file ...", content_length)
    with download_path.open("wb") as file_target:
        bytes_downloaded = 0
        for chunk in response.iter_content(chunk_size=10_485_760):  # 10 MB
            bytes_downloaded += len(chunk)
            percent_downloaded = (bytes_downloaded / content_length) * 100
            logger.debug(
                ">> downloaded {} of {} bytes ({:.2f}%)",
                bytes_downloaded,
                content_length,
                percent_downloaded,
            )
            file_target.write(chunk)


DOWNLOAD_DIR.mkdir(exist_ok=True)

zip_file_paths: list[Path] = []
for download in DOWNLOADS:
    kaggle_path = download
    download_name = kaggle_path.replace("/", "_") + ".zip"
    download_zip = Path(download_name)
    download_path = DOWNLOAD_DIR.joinpath(download_zip)
    zip_file_paths.append(download_path)

    if download_path.exists():
        logger.info("File already downloaded: {}", download_path)
    else:
        logger.info("Downloading file: {}", download_path)
        _download_kaggle_data(kaggle_path, download_path)

for zip_file_path in zip_file_paths:
    with ZipFile(zip_file_path) as zip_file:
        extraction_path = DOWNLOAD_DIR.joinpath(zip_file_path.stem)
        if extraction_path.exists() and list(extraction_path.iterdir()):
            logger.info("Zip already extractd: {}", zip_file_path)
        else:
            logger.info("Extracting {} to {}", zip_file_path, extraction_path)
            zip_file.extractall(extraction_path)

logger.info("Connecting to write database")
connection = sqlite3.connect("features.db")
cursor = connection.cursor()
logger.debug("Creating table if necessary")
cursor.execute(
    "CREATE TABLE IF NOT EXISTS features ("
    "acousticness NUMERIC, "
    "beats_per_minute NUMERIC, "
    "danceability NUMERIC, "
    "duration_ms INTEGER, "
    "energy NUMERIC, "
    "explicit INTEGER, "
    "genre TEXT, "
    "instrumentalness NUMERIC, "
    "isrc TEXT, "
    "key NUMERIC, "
    "liveness NUMERIC, "
    "loudness NUMERIC, "
    "mode NUMERIC, "
    "popularity NUMERIC, "
    "primary_artist TEXT, "
    "speechiness NUMERIC, "
    "spotify_id TEXT PRIMARY KEY, "
    "tempo NUMERIC, "
    "time_signature NUMERIC, "
    "track_name TEXT, "
    "valence NUMERIC, "
    "year INTEGER"
    ")"
)
connection.commit()


# This section will always run
try:
    for kaggle_path, schema in DOWNLOADS.items():
        # There may be tools like pandas to speed this up dramatically
        # will see if that's necessary first.
        directory_name = kaggle_path.replace("/", "_")
        extracted_directory = DOWNLOAD_DIR.joinpath(directory_name)
        logger.debug("Reading files from: {}", extracted_directory)
        for file in schema.filenames:
            data_file = extracted_directory.joinpath(file)
            cursor = connection.cursor()
            counter = 0
            with data_file.open("r") as file_in:
                reader = csv.DictReader(file_in)
                for row in reader:
                    # logger.debug("  row: {}", row)
                    write_dict = {}
                    for column_name, column_meta in schema.column_map.items():
                        datum = row.get(column_name)
                        target_column = column_meta.new_key
                        if datum:
                            if column_meta.new_key == CsvFeature.SPOTIFY_URI:
                                write_dict[CsvFeature.SPOTIFY_ID] = datum.split(":")[-1]
                            else:
                                write_dict[target_column] = datum
                    # logger.debug("  write_dict: {}", { str(k): v for k, v in write_dict.items() } )

                    insert_str = (
                        "INSERT INTO features ("  # noqa: S608
                        f"{', '.join(write_dict.keys())}"
                        ") VALUES ("
                        f"{', '.join(['?' for _ in write_dict])}"
                        ")"
                    )
                    update_str = (
                        f"UPDATE features SET {'=? , '.join(write_dict.keys())}=?"  # noqa: S608
                    )

                    use_isrc_for_pk = False

                    if not write_dict or not write_dict.get(CsvFeature.SPOTIFY_ID):
                        isrc = write_dict.get(CsvFeature.ISRC)
                        if isrc:
                            update_str += "WHERE isrc=?"
                            use_isrc_for_pk = True
                        else:
                            logger.warning("No spotify ID or ISRC found: {}", row)
                        continue
                    else:
                        update_str += "WHERE spotify_id=?"

                    try:
                        cursor.execute(insert_str, list(write_dict.values()))
                    except sqlite3.IntegrityError:
                        cursor.execute(
                            update_str,
                            [
                                *list(write_dict.values()),
                                write_dict[CsvFeature.ISRC]
                                if use_isrc_for_pk
                                else write_dict[CsvFeature.SPOTIFY_ID],
                            ],
                        )
                    except sqlite3.OperationalError:
                        logger.error("Error structuring SQL statement")
                        logger.error("  insert_str: {}", insert_str)
                        logger.error("  update_str: {}", update_str)
                        raise

                    counter += 1
                    if counter > 100:  # noqa: PLR2004
                        connection.commit()
                        counter = 0

            connection.commit()
finally:
    connection.close()
