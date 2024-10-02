import logging
import secrets
import string
from base64 import b64encode
from urllib.parse import ParseResult, urlencode

import requests
from flask import Blueprint, redirect, request, session
from sqlalchemy import select, update
from werkzeug.wrappers.response import Response

from mixtapestudy.config import SPOTIFY_BASE_URL, get_config
from mixtapestudy.database import User, get_session

logger = logging.getLogger(__name__)

auth = Blueprint("auth", __name__)


class OAuthError(Exception):
    pass


@auth.route("/login")
def login() -> Response:
    session.clear()
    config = get_config()
    params: dict[str, str] = {
        "response_type": "code",
        "client_id": config.spotify_client_id,
        "scope": "playlist-modify-public "
        "playlist-modify-private "
        "user-read-recently-played "
        "user-read-currently-playing "
        "user-read-email",
        "redirect_uri": f"{config.oauth_redirect_base_url}/oauth-callback",
        "state": "".join(
            secrets.choice(string.ascii_letters + string.digits) for _ in range(16)
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


@auth.route("/logout")
def logout() -> Response:
    session.clear()
    return redirect("/")


@auth.route("/oauth-callback")
def oauth_callback() -> Response:
    config = get_config()

    code = request.args.get("code")
    error_message = request.args.get("error")
    # TODO: Validate the state; state = request.args.get("state")

    if error_message:
        logger.error(error_message)
        raise OAuthError(error_message)  # TODO: Replace with good error messaging

    token_url = ParseResult(
        scheme="https",
        netloc="accounts.spotify.com",
        path="api/token",
        params="",
        query="",
        fragment="",
    ).geturl()

    encoded_auth = b64encode(
        bytes(f"{config.spotify_client_id}:{config.spotify_client_secret}", "utf8"),
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
        timeout=30,
    )
    token_response.raise_for_status()

    access_token = token_response.json().get("access_token")
    scope = token_response.json().get("scope")
    refresh_token = token_response.json().get("refresh_token")

    me_response = requests.get(
        url=f"{SPOTIFY_BASE_URL}/me",
        headers={
            "Authorization": f"Bearer {access_token}",
        },
        timeout=30,
    )
    me_response.raise_for_status()

    user_id = me_response.json().get("id")
    display_name = me_response.json().get("display_name")
    user_email = me_response.json().get("email")

    with get_session() as db_session:
        existing_user = db_session.scalars(
            select(User).where(User.spotify_id == user_id),
        ).one_or_none()
        # There's a minor race condition here, fix it if necessary
        if existing_user:
            db_session.execute(
                update(User)
                .where(User.spotify_id == user_id)
                .values(
                    spotify_id=user_id,
                    display_name=display_name,
                    email=user_email,
                    access_token=access_token,
                    token_scope=scope,
                    refresh_token=refresh_token,
                ),
            )
            session["id"] = existing_user.id
        else:
            new_user = User(
                spotify_id=user_id,
                display_name=display_name,
                email=user_email,
                access_token=access_token,
                token_scope=scope,
                refresh_token=refresh_token,
            )
            db_session.add(new_user)
            db_session.flush()
            session["id"] = new_user.id

    session["display_name"] = display_name

    return redirect("/search")
