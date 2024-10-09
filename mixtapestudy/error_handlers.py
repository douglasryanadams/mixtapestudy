from uuid import uuid4

from flask import Response, redirect, render_template, session
from loguru import logger
from requests import HTTPError

from mixtapestudy.errors import UserDatabaseRowMissingError, UserIDMissingError


def handle_user_id_missing(_: UserIDMissingError) -> Response:
    logger.warning("Request received missing user ID, sending them to the login page")
    return redirect("/")


def handle_user_missing(_: UserDatabaseRowMissingError) -> Response:
    logger.warning(
        "Request received ID for user missing from the database, "
        "sending them to the login page"
    )
    return redirect("/")


def handle_generic_errors(error: Exception) -> (str, int):
    error_code = uuid4()
    try:
        user_id = session.get("id")
        error.add_note(f"Error code: {error_code}")
        error.add_note(f"User ID: {user_id}")
        logger.exception(error)
    except Exception as error_handling_error:  # noqa: BLE001
        logger.exception(error_handling_error)
    finally:
        return render_template("500_error.html.j2", error_code=error_code), 500  # noqa: B012


def handle_http_request_error(error: HTTPError) -> (str, int):
    try:
        error.add_note(f"Request: {error.request}")
        error.add_note(f"Request headers: {error.request.headers}")
        error.add_note(f"Request body: {error.request.body}")
        error.add_note(f"Response: {error.response}")
        error.add_note(f"Response headers: {error.response.headers}")
        error.add_note(f"Response body: {error.response.text}")
    except Exception as error_handling_error:  # noqa: BLE001
        logger.exception(error_handling_error)
    finally:
        return handle_generic_errors(error)  # noqa: B012
