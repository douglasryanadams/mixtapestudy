import pytest
from flask.testing import FlaskClient

from mixtapestudy.errors import UserIDMissingError

# TODO: Tests for table
# TODO: Tests for edge cases


def test_load_without_session(client_without_session: FlaskClient) -> None:
    with pytest.raises(UserIDMissingError):
        client_without_session.post("/playlist/preview")
