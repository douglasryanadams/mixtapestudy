from uuid import uuid4

from flask import Response, redirect, render_template, request
from loguru import logger
from requests import HTTPError
from werkzeug.exceptions import HTTPException, NotFound

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
        error.add_note(f"Error code: {error_code}")
        logger.exception(error)
    except Exception:  # noqa: BLE001
        logger.exception("Unexpected exception while handling generic error")
    finally:
        return (  # noqa: B012
            render_template("500_error.html.j2", error_code=str(error_code)[24:]),
            500,
        )


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


def handle_404_not_found(error: NotFound) -> (str, int):
    error_code = uuid4()
    try:
        error.add_note(f"Error code: {error_code}")
        logger.debug("Unknown page requested: {}", request.path)
    except Exception:  # noqa: BLE001
        logger.exception("Unexpected exception while handling Not Found error")
    finally:
        return (  # noqa: B012
            render_template("404_error.html.j2", error_code=str(error_code)[24:]),
            404,
        )


def handle_dev_null_bots(_: HTTPException) -> (str, int):
    return "Bad Gateway", 502
