import csv
import sqlite3
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from sqlite3 import Connection
from zipfile import ZipFile

import requests
from loguru import logger

from track_data.logsetup import setup_logger

# Note: This file doesn't have unit tests, it either works or it doesn't
# because the HTTP calls are cached and long running.

setup_logger(logger)


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
    artist = "artist"
    SPEECHINESS = "speechiness"
    SPOTIFY_ID = "spotify_id"
    SPOTIFY_URI = "spotify_uri"  # This is special, it needs parsing
    TEMPO = "tempo"
    TIME_SIGNATURE = "time_signature"
    TRACK_NAME = "track_name"
    VALENCE = "valence"
    YEAR = "year"


@dataclass
class Download:
    filenames: list[str]
    csv_key: dict[str, CsvFeature]
    search_spotify_id: bool = False


KAGGLE_BASE_URL = "https://www.kaggle.com/api/v1/datasets/download"
DOWNLOAD_DIR = Path("../download/")

# This section of the script is huge, but makes it much easier
# to add new sources of data as they're discovered.
# It also makes it possible for others using this repo to rebuild
# the data cache from these files.
DOWNLOADS: dict[str, Download] = {
    "rodolfofigueroa/spotify-12m-songs": Download(
        filenames=["tracks_features.csv"],
        csv_key={
            "acousticness": CsvFeature.ACOUSTICNESS,
            "artists": CsvFeature.artist,
            "danceability": CsvFeature.DANCEABILITY,
            "duration_ms": CsvFeature.DURATION_MS,
            "energy": CsvFeature.ENERGY,
            "explicit": CsvFeature.EXPLICIT,
            "id": CsvFeature.SPOTIFY_ID,
            "instrumentalness": CsvFeature.INSTRUMENTALNESS,
            "key": CsvFeature.KEY,
            "liveness": CsvFeature.LIVENESS,
            "loudness": CsvFeature.LOUDNESS,
            "mode": CsvFeature.MODE,
            "name": CsvFeature.TRACK_NAME,
            "speechiness": CsvFeature.SPEECHINESS,
            "tempo": CsvFeature.TEMPO,
            "time_signature": CsvFeature.TIME_SIGNATURE,
            "valence": CsvFeature.VALENCE,
            "year": CsvFeature.YEAR,
        },
    ),
    "mcfurland/10-m-beatport-tracks-spotify-audio-features": Download(
        # These files are different from the others in that they each have
        # partial data, the order is important in this case because
        # we'll use the cached values from the first file to write the
        # data from the second file in the appropriate rows
        filenames=["sp_track.csv", "audio_features.csv"],
        csv_key={
            "acousticness": CsvFeature.ACOUSTICNESS,
            "danceability": CsvFeature.DANCEABILITY,
            "duration_ms": CsvFeature.DURATION_MS,
            "energy": CsvFeature.ENERGY,
            "explicit": CsvFeature.EXPLICIT,
            "instrumentalness": CsvFeature.INSTRUMENTALNESS,
            "isrc": CsvFeature.ISRC,
            "key": CsvFeature.KEY,
            "liveness": CsvFeature.LIVENESS,
            "loudness": CsvFeature.LOUDNESS,
            "mode": CsvFeature.MODE,
            "speechiness": CsvFeature.SPEECHINESS,
            "tempo": CsvFeature.TEMPO,
            "time_signature": CsvFeature.TIME_SIGNATURE,
            "track_id": CsvFeature.SPOTIFY_ID,
            "track_title": CsvFeature.TRACK_NAME,
            "valence": CsvFeature.VALENCE,
        },
    ),
    "maharshipandya/-spotify-tracks-dataset": Download(
        filenames=["dataset.csv"],
        csv_key={
            "acousticness": CsvFeature.ACOUSTICNESS,
            "artists": CsvFeature.artist,
            "danceability": CsvFeature.DANCEABILITY,
            "duration_ms": CsvFeature.DURATION_MS,
            "energy": CsvFeature.ENERGY,
            "explicit": CsvFeature.EXPLICIT,
            "instrumentalness": CsvFeature.INSTRUMENTALNESS,
            "liveness": CsvFeature.LIVENESS,
            "loudness": CsvFeature.LOUDNESS,
            "popularity": CsvFeature.POPULARITY,
            "speechiness": CsvFeature.SPEECHINESS,
            "tempo": CsvFeature.TEMPO,
            "track_genre": CsvFeature.GENRE,
            "track_id": CsvFeature.SPOTIFY_ID,
            "track_name": CsvFeature.TRACK_NAME,
            "valence": CsvFeature.VALENCE,
        },
    ),
    "solomonameh/spotify-music-dataset": Download(
        filenames=[
            "high_popularity_spotify_data.csv",
            "low_popularity_spotify_data.csv",
        ],
        csv_key={
            "acousticness": CsvFeature.ACOUSTICNESS,
            "danceability": CsvFeature.DANCEABILITY,
            "duration_ms": CsvFeature.DURATION_MS,
            "energy": CsvFeature.ENERGY,
            "id": CsvFeature.SPOTIFY_ID,
            "instrumentalness": CsvFeature.INSTRUMENTALNESS,
            "key": CsvFeature.KEY,
            "liveness": CsvFeature.LIVENESS,
            "loudness": CsvFeature.LOUDNESS,
            "mode": CsvFeature.MODE,
            "playlist_genre": CsvFeature.GENRE,
            "speechiness": CsvFeature.SPEECHINESS,
            "tempo": CsvFeature.TEMPO,
            "time_signature": CsvFeature.TIME_SIGNATURE,
            "track_artist": CsvFeature.artist,
            "track_name": CsvFeature.TRACK_NAME,
            "track_popularity": CsvFeature.POPULARITY,
            "valence": CsvFeature.VALENCE,
        },
    ),
    "joebeachcapital/30000-spotify-songs": Download(
        filenames=["spotify_songs.csv"],
        csv_key={
            "acousticness": CsvFeature.ACOUSTICNESS,
            "danceability": CsvFeature.DANCEABILITY,
            "duration_ms": CsvFeature.DURATION_MS,
            "energy": CsvFeature.ENERGY,
            "instrumentalness": CsvFeature.ENERGY,
            "key": CsvFeature.KEY,
            "liveness": CsvFeature.LIVENESS,
            "loudness": CsvFeature.LOUDNESS,
            "mode": CsvFeature.MODE,
            "playlist_genre": CsvFeature.GENRE,
            "speechiness": CsvFeature.SPEECHINESS,
            "tempo": CsvFeature.TEMPO,
            "track_artist": CsvFeature.artist,
            "track_id": CsvFeature.SPOTIFY_ID,
            "track_name": CsvFeature.TRACK_NAME,
            "track_popularity": CsvFeature.POPULARITY,
            "valence": CsvFeature.VALENCE,
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
        csv_key={
            "acousticness": CsvFeature.ACOUSTICNESS,
            "artist": CsvFeature.artist,
            "danceability": CsvFeature.DANCEABILITY,
            "duration_ms": CsvFeature.DURATION_MS,
            "energy": CsvFeature.ENERGY,
            "instrumentalness": CsvFeature.INSTRUMENTALNESS,
            "key": CsvFeature.KEY,
            "liveness": CsvFeature.LIVENESS,
            "loudness": CsvFeature.LOUDNESS,
            "mode": CsvFeature.MODE,
            "speechiness": CsvFeature.SPEECHINESS,
            "tempo": CsvFeature.TEMPO,
            "time_signature": CsvFeature.TIME_SIGNATURE,
            "track": CsvFeature.TRACK_NAME,
            "uri": CsvFeature.SPOTIFY_URI,
            "valence": CsvFeature.VALENCE,
        },
    ),
    "byomokeshsenapati/spotify-song-attributes": Download(
        filenames=["Spotify_Song_Attributes.csv"],
        csv_key={
            "acousticness": CsvFeature.ACOUSTICNESS,
            "artistName": CsvFeature.artist,
            "danceability": CsvFeature.DANCEABILITY,
            "duration_ms": CsvFeature.DURATION_MS,
            "energy": CsvFeature.ENERGY,
            "genre": CsvFeature.GENRE,
            "id": CsvFeature.SPOTIFY_ID,
            "instrumentalness": CsvFeature.INSTRUMENTALNESS,
            "key": CsvFeature.KEY,
            "liveness": CsvFeature.LIVENESS,
            "loudness": CsvFeature.LOUDNESS,
            "mode": CsvFeature.MODE,
            "speechiness": CsvFeature.SPEECHINESS,
            "tempo": CsvFeature.TEMPO,
            "time_signature": CsvFeature.TIME_SIGNATURE,
            "trackName": CsvFeature.TRACK_NAME,
            "valence": CsvFeature.VALENCE,
        },
    ),
    "gauthamvijayaraj/spotify-tracks-dataset-updated-every-week": Download(
        filenames=["spotify_tracks.csv"],
        csv_key={
            "acousticness": CsvFeature.ACOUSTICNESS,
            "artist_name": CsvFeature.artist,
            "danceability": CsvFeature.DANCEABILITY,
            "duration_ms": CsvFeature.DURATION_MS,
            "energy": CsvFeature.ENERGY,
            "instrumentalness": CsvFeature.INSTRUMENTALNESS,
            "key": CsvFeature.KEY,
            "liveness": CsvFeature.LIVENESS,
            "loudness": CsvFeature.LOUDNESS,
            "mode": CsvFeature.MODE,
            "popularity": CsvFeature.POPULARITY,
            "speechiness": CsvFeature.SPEECHINESS,
            "tempo": CsvFeature.TEMPO,
            "time_signature": CsvFeature.TIME_SIGNATURE,
            "track_id": CsvFeature.SPOTIFY_ID,
            "track_name": CsvFeature.TRACK_NAME,
            "valence": CsvFeature.VALENCE,
            "year": CsvFeature.YEAR,
        },
    ),
    # TODO: Doesn't have Spotify ID or ISRC
    "vicsuperman/prediction-of-music-genre": Download(
        filenames=["music_genre.csv"],
        csv_key={
            "acousticness": CsvFeature.ACOUSTICNESS,
            "artist_name": CsvFeature.artist,
            "danceability": CsvFeature.DANCEABILITY,
            "duration_ms": CsvFeature.DURATION_MS,
            "energy": CsvFeature.ENERGY,
            "instrumentalness": CsvFeature.INSTRUMENTALNESS,
            "key": CsvFeature.KEY,
            "liveness": CsvFeature.LIVENESS,
            "loudness": CsvFeature.LOUDNESS,
            "mode": CsvFeature.MODE,
            "music_genre": CsvFeature.GENRE,
            "popularity": CsvFeature.POPULARITY,
            "speechiness": CsvFeature.SPEECHINESS,
            "tempo": CsvFeature.TEMPO,
            "track_name": CsvFeature.TRACK_NAME,
            "valence": CsvFeature.VALENCE,
        },
        search_spotify_id=True,
    ),
    "gulczas/spotify-dataset": Download(
        filenames=["Spotify_Dataset.csv"],
        csv_key={
            "acousticness": CsvFeature.ACOUSTICNESS,
            "artist_name": CsvFeature.artist,
            "danceability": CsvFeature.DANCEABILITY,
            "duration_ms": CsvFeature.DURATION_MS,
            "energy": CsvFeature.ENERGY,
            "instrumentalness": CsvFeature.INSTRUMENTALNESS,
            "key": CsvFeature.KEY,
            "liveness": CsvFeature.LIVENESS,
            "loudness": CsvFeature.LOUDNESS,
            "mode": CsvFeature.MODE,
            "music_genre": CsvFeature.GENRE,
            "popularity": CsvFeature.POPULARITY,
            "speechiness": CsvFeature.SPEECHINESS,
            "tempo": CsvFeature.TEMPO,
            "track_name": CsvFeature.TRACK_NAME,
            "valence": CsvFeature.VALENCE,
        },
        search_spotify_id=True,
    ),
    "vatsalmavani/spotify-dataset": Download(
        filenames=["data/data.csv"],
        csv_key={
            "acousticness": CsvFeature.ACOUSTICNESS,
            "artist_name": CsvFeature.artist,
            "danceability": CsvFeature.DANCEABILITY,
            "duration_ms": CsvFeature.DURATION_MS,
            "energy": CsvFeature.ENERGY,
            "instrumentalness": CsvFeature.INSTRUMENTALNESS,
            "key": CsvFeature.KEY,
            "liveness": CsvFeature.LIVENESS,
            "loudness": CsvFeature.LOUDNESS,
            "mode": CsvFeature.MODE,
            "music_genre": CsvFeature.GENRE,
            "popularity": CsvFeature.POPULARITY,
            "speechiness": CsvFeature.SPEECHINESS,
            "tempo": CsvFeature.TEMPO,
            "track_name": CsvFeature.TRACK_NAME,
            "valence": CsvFeature.VALENCE,
        },
        search_spotify_id=True,
    ),
    "sanjanchaudhari/spotify-dataset": Download(
        filenames=["cleaned_dataset.csv"],
        csv_key={
            "acousticness": CsvFeature.ACOUSTICNESS,
            "artist_name": CsvFeature.artist,
            "danceability": CsvFeature.DANCEABILITY,
            "duration_ms": CsvFeature.DURATION_MS,
            "energy": CsvFeature.ENERGY,
            "instrumentalness": CsvFeature.INSTRUMENTALNESS,
            "key": CsvFeature.KEY,
            "liveness": CsvFeature.LIVENESS,
            "loudness": CsvFeature.LOUDNESS,
            "mode": CsvFeature.MODE,
            "music_genre": CsvFeature.GENRE,
            "popularity": CsvFeature.POPULARITY,
            "speechiness": CsvFeature.SPEECHINESS,
            "tempo": CsvFeature.TEMPO,
            "track_name": CsvFeature.TRACK_NAME,
            "valence": CsvFeature.VALENCE,
        },
        search_spotify_id=True,
    ),
    "henrydalrymple/spotify-dataset": Download(
        filenames=["test.csv", "train.csv"],
        csv_key={
            "acousticness": CsvFeature.ACOUSTICNESS,
            "artist_name": CsvFeature.artist,
            "danceability": CsvFeature.DANCEABILITY,
            "duration_ms": CsvFeature.DURATION_MS,
            "energy": CsvFeature.ENERGY,
            "instrumentalness": CsvFeature.INSTRUMENTALNESS,
            "key": CsvFeature.KEY,
            "liveness": CsvFeature.LIVENESS,
            "loudness": CsvFeature.LOUDNESS,
            "mode": CsvFeature.MODE,
            "music_genre": CsvFeature.GENRE,
            "popularity": CsvFeature.POPULARITY,
            "speechiness": CsvFeature.SPEECHINESS,
            "tempo": CsvFeature.TEMPO,
            "track_name": CsvFeature.TRACK_NAME,
            "valence": CsvFeature.VALENCE,
        },
        search_spotify_id=True,
    ),
}


def _download_kaggle_data(kaggle_path: str, download_path: Path) -> None:
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


def create_features_table(connection: Connection) -> None:
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
        "artist TEXT, "
        "speechiness NUMERIC, "
        "spotify_id TEXT PRIMARY KEY, "
        "tempo NUMERIC, "
        "time_signature NUMERIC, "
        "track_name TEXT, "
        "valence NUMERIC, "
        "year INTEGER"
        ")"
    )
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_isrc ON features (isrc)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_track_name ON features (track_name)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_artist ON features (artist)")
    cursor.execute(
        "CREATE TABLE IF NOT EXISTS progress ("
        "download TEXT PRIMARY KEY, "
        "last_position INTEGER, "
        "complete INTEGER"
        ")"
    )
    connection.commit()


def _download_files() -> list[Path]:
    zip_file_paths = []
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
    return zip_file_paths


def _unzip_files(zip_file_paths: list[Path]) -> None:
    for zip_file_path in zip_file_paths:
        with ZipFile(zip_file_path) as zip_file:
            extraction_path = DOWNLOAD_DIR.joinpath(zip_file_path.stem)
            if extraction_path.exists() and list(extraction_path.iterdir()):
                logger.info("Zip already extractd: {}", zip_file_path)
            else:
                logger.info("Extracting {} to {}", zip_file_path, extraction_path)
                zip_file.extractall(extraction_path)


# TODO: Simplify this method and refactor
def main() -> None:  # noqa: C901, PLR0912, PLR0915
    DOWNLOAD_DIR.mkdir(exist_ok=True)

    zip_file_paths = _download_files()

    _unzip_files(zip_file_paths)

    logger.info("Connecting to write database")
    connection = sqlite3.connect("../features.db")

    create_features_table(connection)

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
                try:
                    cursor.execute(
                        "INSERT INTO progress (download, last_position, complete) "
                        "VALUES (?, 0, 0)",
                        (str(data_file),),
                    )
                    connection.commit()
                    counter = 0
                    logger.info("New file ({}), starting from beginning", data_file)
                except sqlite3.IntegrityError:
                    counter_found = cursor.execute(
                        "SELECT last_position, complete FROM progress WHERE download=?",
                        (str(data_file),),
                    ).fetchone()
                    counter = int(counter_found[0])
                    complete = bool(counter_found[1])
                    if complete:
                        logger.info(
                            "Already loaded this file completely: {}", data_file
                        )
                        continue

                    logger.info(
                        "Already loaded some of this file ({}), starting from: {}",
                        data_file,
                        counter,
                    )

                with data_file.open("r") as file_in:
                    reader = csv.DictReader(file_in)
                    for _ in range(counter):
                        next(reader)
                    for row in reader:
                        write_dict = {}
                        for column_name, column_meta in schema.csv_key.items():
                            datum = row.get(column_name)
                            target_column = column_meta.new_key
                            if datum:
                                if column_meta.new_key == CsvFeature.SPOTIFY_URI:
                                    write_dict[CsvFeature.SPOTIFY_ID] = datum.split(
                                        ":"
                                    )[-1]
                                else:
                                    write_dict[target_column] = datum

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
                        select_str = "SELECT 1 FROM features "

                        use_isrc_for_pk = False
                        spotify_id = write_dict.get(CsvFeature.SPOTIFY_ID)

                        if not write_dict or not spotify_id:
                            isrc = write_dict.get(CsvFeature.ISRC)
                            if isrc:
                                update_str += "WHERE isrc=?"
                                select_str += "WHERE isrc=?"
                                use_isrc_for_pk = True
                            else:
                                logger.warning("No spotify ID or ISRC found: {}", row)
                                continue
                        else:
                            update_str += "WHERE spotify_id=?"
                            select_str += "WHERE spotify_id=?"

                        existing_row = cursor.execute(
                            select_str,
                            [isrc if use_isrc_for_pk else spotify_id],
                        ).fetchone()

                        try:
                            if existing_row:
                                cursor.execute(
                                    update_str,
                                    [
                                        *list(write_dict.values()),
                                        isrc if use_isrc_for_pk else spotify_id,
                                    ],
                                )
                            else:
                                cursor.execute(insert_str, list(write_dict.values()))
                        except sqlite3.OperationalError:
                            logger.error("Error structuring SQL statement")
                            logger.error("  insert_str: {}", insert_str)
                            logger.error("  update_str: {}", update_str)
                            raise

                        counter += 1
                        if counter % 100 == 0:
                            cursor.execute(
                                "UPDATE progress SET last_position=? WHERE download=?",
                                (counter, str(data_file)),
                            )
                            connection.commit()

                cursor.execute(
                    "UPDATE progress SET last_position=? WHERE download=?",
                    (counter, str(data_file)),
                )
                connection.commit()
                counter = 0
    finally:
        connection.close()


if __name__ == "__main__":
    main()
