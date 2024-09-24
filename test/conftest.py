import os
import subprocess
import time
from collections.abc import Iterable
from threading import Thread

import requests
from alembic import command, config
from flask import Flask
from flask.testing import FlaskClient
from pytest import fixture, MonkeyPatch

from mixtapestudy.app import create_app
from mixtapestudy.database import get_session


@fixture(autouse=True)
def set_env(monkeypatch):
    monkeypatch.setenv("OAUTH_REDIRECT_BASE_URL", "http://fake-test-domain")
    monkeypatch.setenv("SPOTIFY_CLIENT_ID", "fake-spotify-client-id")
    monkeypatch.setenv("SPOTIFY_CLIENT_SECRET", "fake-spotify-client-secret")
    monkeypatch.setenv("DATABASE_URL", "postgresql://local:admin@localhost:5432/mixtapestudy")


@fixture(autouse=True, scope="session")
def stack():
    up = subprocess.run(["docker-compose up --detach"], check=True, shell=True)
    print(up.args)
    assert up.returncode == 0
    healthcheck = False
    count = 0
    while not healthcheck and count < 60:
        check_response = requests.get("http://localhost/flask-health-check")
        healthcheck = check_response.status_code == 200
        count += 1
        time.sleep(1)

    yield
    down = subprocess.run(["docker-compose down --volumes --remove-orphans migration_done"], check=True, shell=True)
    assert down.returncode == 0


@fixture
def session():
    with get_session() as s:
        yield s


@fixture
def app(stack, set_env) -> Iterable[Flask]:
    app = create_app()
    app.config.update({"TESTING": True})
    yield app


@fixture
def client(app: Flask) -> FlaskClient:
    return app.test_client()
