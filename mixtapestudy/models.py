from dataclasses import dataclass


@dataclass(frozen=True)
class Song:
    uri: str
    id: str
    name: str
    artist: str
