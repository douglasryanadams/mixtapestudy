import inspect
import logging
import sys

from loguru import logger


class InterceptHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        # Get corresponding Loguru level if it exists.
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        # Find caller from where originated the logged message.
        frame, depth = inspect.currentframe(), 0
        while frame and (depth == 0 or frame.f_code.co_filename == logging.__file__):
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(
            level, record.getMessage()
        )


def setup_logger(loguru_logger: logger) -> None:
    loguru_logger.remove()
    logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)
    loguru_logger.add(sys.stdout, colorize=True)

    requests_logger = logging.getLogger("requests.packages.urllib3")
    requests_logger.setLevel(logging.DEBUG)
    requests_logger.propagate = True
