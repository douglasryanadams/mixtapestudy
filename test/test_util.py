from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode

import pytest
from flask.testing import FlaskClient
from requests_mock import adapter
from sqlalchemy.orm import Session

from mixtapestudy.database import User, get_session
from mixtapestudy.errors import UserIDMissingError
from mixtapestudy.routes.util import get_user
from test.conftest import FAKE_ACCESS_TOKEN, FAKE_REFRESH_TOKEN, FAKE_USER_ID


def test_get_user_no_session(client_without_session: FlaskClient) -> None:
    with (
        client_without_session.application.test_request_context(),
        pytest.raises(UserIDMissingError),
    ):
        get_user()


def test_get_user_valid_session(client: FlaskClient) -> None:
    with client.application.test_request_context() as context:
        context.session["id"] = FAKE_USER_ID
        user = get_user()

    assert user.id == FAKE_USER_ID


def test_get_user_expired_token(
    client: FlaskClient, mock_token_refresh: adapter._Matcher, db_session: Session
) -> None:
    with get_session() as db_session_2:
        initial_user = db_session_2.get(User, FAKE_USER_ID)
        initial_user.token_expires = datetime.now(tz=UTC) - timedelta(days=1)
        db_session_2.merge(initial_user)
        db_session_2.commit()

    with client.application.test_request_context() as context:
        context.session["id"] = FAKE_USER_ID
        user = get_user()

    assert user.id == FAKE_USER_ID
    assert mock_token_refresh.called
    assert mock_token_refresh.last_request.text == urlencode(
        {"grant_type": "refresh_token", "refresh_token": FAKE_REFRESH_TOKEN}
    )

    db_user = db_session.get(User, FAKE_USER_ID)
    assert db_user.access_token == f"{FAKE_ACCESS_TOKEN}_new"
    assert db_user.refresh_token == f"{FAKE_REFRESH_TOKEN}_new"
    assert db_user.token_expires == datetime(2020, 1, 1, 1, 0, 0, tzinfo=UTC)
