import json
import logging
from bs4 import BeautifulSoup as soup
import requests


logger = logging.getLogger(__name__)


warning = (
    "Will print the response text (Please be careful as "
    + "this may contain personal data or allow others to login to your account):"
)


def LoginWeb(user, password):
    """Login to itch.io using webscraping"""
    session = requests.Session()

    # GET the page first so we have a valid CSRF token value
    login1 = session.get("https://itch.io/login")
    s = soup(login1.text, "html.parser")
    csrf_token = s.find("input", {"name": "csrf_token"})["value"]

    # Now POST the login
    r = session.post(
        "https://itch.io/login",
        {"username": user, "password": password, "csrf_token": csrf_token},
    )

    if r.status_code != 200:
        raise RuntimeError

    return session


def LoginAPI(user, password):
    """Login to itch.io using API"""
    r = requests.post(
        "https://api.itch.io/login",
        {"username": user, "password": password, "source": "desktop"},
    )
    if r.status_code != 200:
        logger.error("\n".join([
            f"Error: {r.status_code} is not 200",
            warning,
            r.text,
        ]))
        raise RuntimeError
    t = json.loads(r.text)

    if not t["success"]:
        logger.error("\n".join([
            "Error: success key is not true",
            warning,
            r.text,
        ]))
        raise RuntimeError

    return t["key"]["key"]
