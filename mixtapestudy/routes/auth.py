import logging
import random
import string
from base64 import b64encode

import requests
from flask import Blueprint, redirect, request
from urllib.parse import ParseResult, urlencode


from mixtapestudy.database import get_session, User
from mixtapestudy.env import get_config, SPOTIFY_BASE_URL

logger = logging.getLogger(__name__)

auth = Blueprint("auth", __name__)


@auth.route("/login")
def login():
    config = get_config()
    params: dict[str, str] = {
        "response_type": "code",
        "client_id": config.spotify_client_id,
        "scope": "playlist-modify-public playlist-modify-private user-read-recently-played user-read-currently-playing user-read-email",
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
    token_response = requests.post(
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
    token_response.raise_for_status()

    access_token = token_response.json().get("access_token")
    scope = token_response.json().get("scope")
    refresh_token = token_response.json().get("refresh_token")

    me_response = requests.get(f"{SPOTIFY_BASE_URL}/me")
    me_response.raise_for_status()

    user_id = me_response.json().get("id")
    display_name = me_response.json().get("display_name")
    user_email = me_response.json().get("email")

    with get_session() as session:
        session.add(
            User(
                spotify_id=user_id,
                display_name=display_name,
                email=user_email,
                access_token=access_token,
                token_scope=scope,
                refresh_token=refresh_token,
            )
        )

    return redirect("/search")
