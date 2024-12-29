import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import TextIO


@dataclass
class SpotifyTrack:
    end_time: str
    artist_name: str
    track_name: str
    ms_played: int


@dataclass
class ApiTrack: ...


@dataclass
class CsvTrack:
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


def get_features(tracks: list[SpotifyTrack]) -> list[ApiTrack]: ...


def convert_to_csv(tracks: list[ApiTrack]) -> str: ...


def write_csv(filepath: str, csv_input: str) -> None:
    with Path(filepath).open("w") as csv_out:
        csv_out.write(csv_input)


def main(filepath: str) -> None:
    with Path(filepath).open("r") as json_input:
        tracks_loaded = load_history(json_input)
    tracks_features = get_features(tracks_loaded)
    csv_text = convert_to_csv(tracks_features)
    write_csv(filepath, csv_text)


if __name__ == "__main__":
    main(sys.argv[1])
