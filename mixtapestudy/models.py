from dataclasses import dataclass


@dataclass(frozen=True)
class Song:
    id: str
    name: str
    artist: str
