from datetime import datetime, timezone

import pytest
from requests_mock import Mocker, adapter
from sqlalchemy.orm import Session

from mixtapestudy.config import SPOTIFY_BASE_URL
from mixtapestudy.database import User
from test.conftest import FAKE_ACCESS_TOKEN, FAKE_REFRESH_TOKEN


@pytest.fixture
def fake_users(db_session: Session) -> list[User]:
    users = []
    for n in range(1, 10):
        user = User(
            spotify_id=f"fake_spotify_id_{n}",
            email=f"fake_email_{n}@email.email",
            display_name=f"Fake Spotify Name {n}",
            access_token=FAKE_ACCESS_TOKEN,
            token_scope="fake-scope",
            token_expires=datetime(2000, 0, 0, tzinfo=timezone.utc),
            refresh_token=FAKE_REFRESH_TOKEN,
        )
        users.append(user)
        db_session.add(user)

    db_session.commit()
    return users


@pytest.fixture
def mock_history_request(requests_mock: Mocker) -> adapter._Matcher:
    params = {"limit": 50}
    return requests_mock.get(
        f"{SPOTIFY_BASE_URL}/me/player/recently-played",
        request_headers={"Authorization": f"Bearer {FAKE_ACCESS_TOKEN}"},
        # This is a dramatically simplified version of this response
        # For full example see:
        #   https://developer.spotify.com/documentation/web-api/reference/get-recently-played
        json={"items": [{"track": ""}]},
    )


def test_pull_history() -> None: ...


def test_pull_history_by_user() -> None: ...


def test_pull_history_rate_limited() -> None: ...


def test_pull_history_spotify_error() -> None: ...
