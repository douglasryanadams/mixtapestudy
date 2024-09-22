import logging
import os
import random
import string
import sys
from base64 import b64encode
from urllib.parse import ParseResult, urlencode

import requests
from flask import Flask, request, jsonify, render_template, redirect

logging.basicConfig(level=logging.DEBUG, stream=sys.stdout, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
requests_logger = logging.getLogger("requests.packages.urllib3")
requests_logger.setLevel(logging.DEBUG)
requests_logger.propagate= True
logger = logging.getLogger(__name__)

app = Flask(__name__)

OAUTH_REDIRECT_URI = os.getenv('OAUTH_REDIRECT_URI', 'https://mixtapestudy2.com')
logger.debug(f"{OAUTH_REDIRECT_URI=}")
CLIENT_ID = os.getenv('SPOTIFY_CLIENT_ID', '24c831c158dc43b79f6eab9c65a38a6c')
logger.debug(f"{CLIENT_ID=}")
CLIENT_SECRET = os.getenv('SPOTIFY_CLIENT_SECRET')
logger.debug("SPOTIFY_CLIENT_SECRET defined (not shown)")
if not CLIENT_SECRET:
    raise Exception("No CLIENT_SECRET environment variable provided")


@app.route("/")
def home() -> str:
    return render_template("login.html.j2")


@app.route("/login")
def login():
    params: dict[str, str] = {
        "response_type": "code",
        "client_id": CLIENT_ID,
        "scope": "playlist-modify-public playlist-modify-private user-read-recently-played user-read-currently-playing",
        "redirect_uri": f"{OAUTH_REDIRECT_URI}/oauth-callback",
        "state": "".join(
            random.choice(string.ascii_letters + string.digits) for _ in range(16)
        ),
    }
    logger.debug("OAuth query params: %s", params)
    return_url = ParseResult(
        scheme="https",
        netloc="accounts.spotify.com",
        path="authorize",
        params="",
        query=urlencode(params),
        fragment="",
    ).geturl()

    return redirect(return_url)


@app.route("/oauth-callback")
def oauth_callback():
    code = request.args.get("code")
    error = request.args.get("error")
    state = request.args.get("state")  # TODO: Validate the state
    if error:
        raise Exception(error)  # TODO: Replace with good error messaging

    token_url = ParseResult(
        scheme="https",
        netloc="accounts.spotify.com",
        path="api/token",
        params="",
        query="",
        fragment=""
    ).geturl()

    encoded_auth = b64encode(bytes(f"{CLIENT_ID}:{CLIENT_SECRET}", 'utf8')).decode('utf8')
    logger.debug(f"{encoded_auth=}")
    response = requests.post(
        url=token_url,
        data={
            'code': code,
            'redirect_uri': f"{OAUTH_REDIRECT_URI}/oauth-callback",
            'grant_type': 'authorization_code'
        },
        headers={
            'content-type': 'application/x-www-form-urlencoded',
            'Authorization': f"Basic {encoded_auth}"
        }
    )

    access_token = response.json().get("access_token")
    if not access_token:
        raise Exception("No access token received: %s - %s", response, response.text)
    return access_token


@app.route("/info")
def info():
    resp = {
        "connecting_ip": request.headers["X-Real-IP"],
        "proxy_ip": request.headers["X-Forwarded-For"],
        "host": request.headers["Host"],
        "user-agent": request.headers["User-Agent"],
    }

    return jsonify(resp)


@app.route("/flask-health-check")
def flask_health_check():
    return "success"
