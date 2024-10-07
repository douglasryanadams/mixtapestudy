import logging
from datetime import UTC, datetime, timedelta

import requests
from flask import session
from sqlalchemy.orm import Session

from mixtapestudy.config import get_config
from mixtapestudy.data import UserData
from mixtapestudy.database import User, get_session
from mixtapestudy.errors import UserIDMissingError

logger = logging.getLogger(__name__)


def _refresh_token(user: User, session: Session) -> None:
    r = requests.post(
        "https://accounts.spotify.com/api/token",
        data={
            "grant_type": "refresh_token",
            "refresh_token": user.refresh_token,
            "client_id": get_config().spotify_client_id,
        },
        timeout=30,
    )
    r.raise_for_status()

    user.access_token = r.json()["access_token"]
    user.refresh_token = r.json()["refresh_token"]
    expires_in = int(r.json()["expires_in"])
    user.token_expires = datetime.now(tz=UTC) + timedelta(seconds=expires_in)
    user.scope = r.json()["scope"]
    session.merge(user)


def get_user() -> UserData:
    """Return a user from the database from the session.

    This function serves 2 purposes:

    1. Make sure there's an 'id' in the session token (and
    that there is a session token)

    2. Make sure the Spotify token for this user os up to date
    """
    user_id = session.get("id")
    logger.info("Handling request for: %s", user_id)
    if not user_id:
        raise UserIDMissingError

    with get_session() as db_session:
        user = db_session.get(User, user_id)
        logger.debug("User from database: %s", user)

        if user.token_expires < datetime.now(tz=UTC) - timedelta(minutes=5):
            _refresh_token(user, db_session)

        user_dict = {
            column.name: getattr(user, column.name) for column in User.__mapper__.c
        }
        return UserData(**user_dict)
