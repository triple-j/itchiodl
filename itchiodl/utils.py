import logging
import re
import sys
import hashlib
import requests


logger = logging.getLogger(__name__)


class NoDownloadError(Exception):
    """No download found exception"""


def download(url, path, name, file):
    """Downloads a file from a url and saves it to a path, skips it if it already exists."""

    desc = f"{name} - {file}"
    logger.debug(f"Downloading {desc}")
    rsp = requests.get(url, stream=True)

    if (
        rsp.headers.get("content-length") is None
        or rsp.headers.get("Content-Disposition") is None
    ):
        raise NoDownloadError("Http response is not a download, skipping")

    cd = rsp.headers.get("Content-Disposition")

    filename_re = re.search(r'filename="(.+)"', cd)
    if filename_re is None:
        filename = file
    else:
        filename = filename_re.group(1)

    with open(f"{path}/{filename}", "wb") as f:
        for chunk in rsp.iter_content(10240):
            f.write(chunk)

    logger.debug(f"Downloaded {filename}")
    return f"{path}/{filename}", True


def clean_path(path):
    """Cleans a path on windows"""
    if sys.platform in ["win32", "cygwin", "msys"]:
        path_clean = re.replace(r"[\<\>\:\"\/\\\|\?\*]", "-", path)
        return path_clean
    return path


def md5sum(path):
    """Returns the md5sum of a file"""
    md5 = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            md5.update(chunk)
    return md5.hexdigest()


class ColoredLogFormatter(logging.Formatter):
    grey = "\x1b[90m"
    yellow = "\x1b[33m"
    red = "\x1b[31m"
    bold_red = "\x1b[1;31m"
    reset = "\x1b[0m"

    FORMATS = {
        logging.DEBUG: grey,
        logging.INFO: None,
        logging.WARNING: yellow,
        logging.ERROR: red,
        logging.CRITICAL: bold_red
    }

    def format(self, record):
        formatted = super().format(record)
        color = self.FORMATS.get(record.levelno)
        if color is not None:
            formatted = f"{color}{formatted}{self.reset}"
        return formatted
