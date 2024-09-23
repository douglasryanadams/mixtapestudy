from collections.abc import Iterable

from flask import Flask
from flask.testing import FlaskClient
from pytest import fixture, MonkeyPatch

from mixtapestudy.app import create_app


@fixture(autouse=True)
def set_env(monkeypatch):
    monkeypatch.setenv("OAUTH_REDIRECT_BASE_URL", "http://fake-test-domain")
    monkeypatch.setenv("SPOTIFY_CLIENT_ID", "fake-spotify-client-id")
    monkeypatch.setenv("SPOTIFY_CLIENT_SECRET", "fake-spotify-client-secret")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")


@fixture
def app(set_env) -> Iterable[Flask]:
    app = create_app()
    app.config.update({"TESTING": True})
    yield app


@fixture
def client(app: Flask) -> FlaskClient:
    return app.test_client()
