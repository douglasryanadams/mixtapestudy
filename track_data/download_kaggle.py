import inspect
import logging
import sys
from pathlib import Path

import requests
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


logger.remove()
logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)
logger.add(sys.stdout, colorize=True)
requests_logger = logging.getLogger("requests.packages.urllib3")
requests_logger.setLevel(logging.DEBUG)
requests_logger.propagate = True

BASE_URL = "https://www.kaggle.com/api/v1/datasets/download"
DOWNLOAD_PATHS = [
    "rodolfofigueroa/spotify-12m-songs",
    "vicsuperman/prediction-of-music-genre",
    "mcfurland/10-m-beatport-tracks-spotify-audio-features",
    "maharshipandya/-spotify-tracks-dataset",
    "solomonameh/spotify-music-dataset",
    "joebeachcapital/30000-spotify-songs",
    "theoverman/the-spotify-hit-predictor-dataset",
    "byomokeshsenapati/spotify-song-attributes",
    "arnavvvvv/spotify-music",
    "gauthamvijayaraj/spotify-tracks-dataset-updated-every-week",
    "abdulszz/spotify-most-streamed-songs",
    "priyamchoksi/spotify-dataset-114k-songs",
]

for path in DOWNLOAD_PATHS:
    download_name = path.replace("/", "_") + ".zip"
    request_path = f"{BASE_URL}/{path}"

    logger.info("Downloading: {}", request_path)
    response = requests.get(request_path, stream=True, timeout=120)
    logger.debug(">> response: {}", response)
    response.raise_for_status()

    content_length = int(response.headers["content-length"])
    logger.debug(">> writing {} byte file ...", content_length)
    with Path(f"./download/{download_name}").open("wb") as file_target:
        bytes_downloaded = 0
        for chunk in response.iter_content(chunk_size=10_485_760):  # 10 MB
            bytes_downloaded += len(chunk)
            percent_downloaded = (bytes_downloaded / content_length) * 100
            logger.debug(
                ">> downloaded {} of {} bytes ({:.2f}%)",
                bytes_downloaded,
                content_length,
                percent_downloaded,
            )
            file_target.write(chunk)
