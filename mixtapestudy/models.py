from dataclasses import dataclass


@dataclass(frozen=True)
class Song:
    uri: str
    id: str
    name: str
    # Comma Separated String, list of names
    artist: str
    # JSON String, list of names
    artist_raw: str
