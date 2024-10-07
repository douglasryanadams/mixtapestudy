from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class UserData:
    id: UUID
    updated: datetime
    created: datetime
    spotify_id: str
    email: str
    display_name: str
    access_token: str
    token_scope: str
    token_expires: datetime
    refresh_token: str
