from requests import HTTPError


class UserIDMissingError(Exception):
    pass


class MixtapeHTTPError(HTTPError):
    pass
