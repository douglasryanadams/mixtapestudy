from http import HTTPStatus

from bs4 import BeautifulSoup
from flask.testing import FlaskClient


def test_return_with_active_session(client: FlaskClient) -> None:
    """Users who return and were previously logged in, should not have to auth again."""
    r = client.get("/")
    assert r.status_code == HTTPStatus.FOUND
    assert r.headers["Location"] == "/search"


def test_render_login_without_active_session(
    client_without_session: FlaskClient,
) -> None:
    r = client_without_session.get("/")
    assert r.status_code == HTTPStatus.OK

    soup = BeautifulSoup(r.text, "html.parser")
    login_button = soup.find(id="login-button")
    assert login_button.string == "Log in with Spotify"
