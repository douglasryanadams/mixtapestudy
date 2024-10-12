from datetime import UTC, datetime, timedelta

import requests
from flask import g, session
from requests import HTTPError
from requests.auth import HTTPBasicAuth
from sqlalchemy.orm import Session

from mixtapestudy.config import get_config
from mixtapestudy.data import UserData
from mixtapestudy.database import UnexpectedDatabaseError, User, get_session
from mixtapestudy.errors import UserDatabaseRowMissingError, UserIDMissingError


def _refresh_token(user: User, session: Session) -> None:
    config = get_config()
    refresh_response = requests.post(
        "https://accounts.spotify.com/api/token",
        auth=HTTPBasicAuth(config.spotify_client_id, config.spotify_client_secret),
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
        },
        data={
            "grant_type": "refresh_token",
            "refresh_token": user.refresh_token,
        },
        timeout=30,
    )
    try:
        refresh_response.raise_for_status()
    except HTTPError as error:
        g.logger.warning(
            "HTTP Request Failed!\n{}\n{}\n{}",
            error,
            error.response.headers,
            error.response.text,
        )
        raise

    g.logger.debug("  Refresh token response: {}", refresh_response.json())
    user.access_token = refresh_response.json()["access_token"]
    if "refresh_token" in refresh_response.json():
        user.refresh_token = refresh_response.json()["refresh_token"]
    expires_in = int(refresh_response.json()["expires_in"])
    user.token_expires = datetime.now(tz=UTC) + timedelta(seconds=expires_in)
    user.scope = refresh_response.json()["scope"]
    session.merge(user)


def get_user() -> UserData:
    """Return a user from the database from the session.

    This function serves 2 purposes:

    1. Make sure there's an 'id' in the session token (and
    that there is a session token)

    2. Make sure the Spotify token for this user os up to date
    """
    user_id = session.get("id")
    g.logger.info("Handling request for user: {}", user_id)
    if not user_id:
        raise UserIDMissingError

    try:
        with get_session() as db_session:
            user = db_session.get(User, user_id)
            if not user:
                session.clear()
                raise UserDatabaseRowMissingError

            five_minutes_from_now = datetime.now(tz=UTC) + timedelta(minutes=5)
            g.logger.debug("  token_expires: {}", user.token_expires)
            g.logger.debug("  five_minutes_from_now: {}", five_minutes_from_now)
            g.logger.debug(
                "  token_expires - five_minutes_from_now = {}",
                user.token_expires - five_minutes_from_now,
            )
            if user.token_expires < five_minutes_from_now:
                _refresh_token(user, db_session)

            user_dict = {
                column.name: getattr(user, column.name) for column in User.__mapper__.c
            }
            return UserData(**user_dict)
    except UnexpectedDatabaseError as error:
        session.clear()
        raise UserDatabaseRowMissingError from error
