import logging
import random
import string
from base64 import b64encode

import requests
from flask import Blueprint, redirect, request
from urllib.parse import ParseResult, urlencode

from mixtapestudy.env import get_config

logger = logging.getLogger(__name__)

auth = Blueprint("auth", __name__)


@auth.route("/login")
def login():
    config = get_config()
    params: dict[str, str] = {
        "response_type": "code",
        "client_id": config.spotify_client_id,
        "scope": "playlist-modify-public playlist-modify-private user-read-recently-played user-read-currently-playing",
        "redirect_uri": f"{config.oauth_redirect_base_url}/oauth-callback",
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


@auth.route("/oauth-callback")
def oauth_callback():
    config = get_config()

    code = request.args.get("code")
    error = request.args.get("error")
    # state = request.args.get("state")  # TODO: Validate the state
    if error:
        raise Exception(error)  # TODO: Replace with good error messaging

    token_url = ParseResult(
        scheme="https",
        netloc="accounts.spotify.com",
        path="api/token",
        params="",
        query="",
        fragment="",
    ).geturl()

    encoded_auth = b64encode(
        bytes(f"{config.spotify_client_id}:{config.spotify_client_secret}", "utf8")
    ).decode("utf8")
    response = requests.post(
        url=token_url,
        data={
            "code": code,
            "redirect_uri": f"{config.oauth_redirect_base_url}/oauth-callback",
            "grant_type": "authorization_code",
        },
        headers={
            "content-type": "application/x-www-form-urlencoded",
            "Authorization": f"Basic {encoded_auth}",
        },
    )

    response.raise_for_status()

    # TODO: Write to database
    # access_token = response.json().get("access_token")
    # scope = response.json().get("scope")
    # refresh_token = response.json().get("refresh_token")
    # expires_in = response.json().get("expires_in")
    return redirect("/search")
