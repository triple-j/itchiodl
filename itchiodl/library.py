import json
from concurrent.futures import ThreadPoolExecutor
import functools
import logging
from sys import stderr
import threading
from traceback import print_tb
import requests
from bs4 import BeautifulSoup

from itchiodl.game import DownloadStatus, Game


logger = logging.getLogger(__name__)


class Library:
    """Representation of a user's game library"""

    def __init__(self, login, jobs=4):
        self.login = login
        self.games = []
        self.jobs = jobs

    def load_game_page(self, page):
        """Load a page of games via the API"""
        logger.debug(f"Loading page {page}")
        r = requests.get(
            f"https://api.itch.io/profile/owned-keys?page={page}",
            headers={"Authorization": self.login},
        )
        j = json.loads(r.text)

        for s in j["owned_keys"]:
            self.games.append(Game(s))

        return len(j["owned_keys"])

    def load_owned_games(self):
        """Load all games in the library via the API"""
        page = 1
        while True:
            n = self.load_game_page(page)
            if n == 0:
                break
            page += 1

    def load_game(self, publisher, title):
        """Load a game by publisher and title"""
        rsp = requests.get(
            f"https://{publisher}.itch.io/{title}/data.json",
            headers={"Authorization": self.login},
        )
        j = json.loads(rsp.text)
        game_id = j["id"]
        gsp = requests.get(
            f"https://api.itch.io/games/{game_id}",
            headers={"Authorization": self.login},
        )
        k = json.loads(gsp.text)
        self.games.append(Game(k))

    def load_games(self, publisher):
        """Load all games by publisher"""
        rsp = requests.get(f"https://{publisher}.itch.io")
        soup = BeautifulSoup(rsp.text, "html.parser")
        for link in soup.select("a.game_link"):
            game_id = link.get("data-label").split(":")[1]
            gsp = requests.get(
                f"https://api.itch.io/games/{game_id}",
                headers={"Authorization": self.login},
            )
            k = json.loads(gsp.text)
            self.games.append(Game(k))

    def download_library(self, platform=None):
        """Download all games in the library"""
        statuses = []
        if self.jobs <= 1:
            logger.debug("Run without Threading")
            l = len(self.games)
            for (i, g) in enumerate(self.games):
                x = g.download(self.login, platform)
                logger.debug(f"Downloaded {g.name} ({i+1} of {l})")
                statuses.append({
                    "name": g.name,
                    "statuses": x
                })
        else:
            logger.debug(f"Run {self.jobs} Threads")
            with ThreadPoolExecutor(max_workers=self.jobs) as executor:
                i = [0]
                l = len(self.games)
                lock = threading.RLock()

                def dl(i, g):
                    try:
                        x = g.download(self.login, platform)
                    except Exception as e:
                        x = [{
                            "filename": "UNKNOWN",
                            "status": e
                        }]
                    with lock:
                        i[0] += 1
                    logger.debug(f"Downloaded {g.name} ({i[0]} of {l})")
                    return {
                        "name": g.name,
                        "statuses": x
                    }

                for result in executor.map(functools.partial(dl, i), self.games):
                    statuses.append(result)

        # Summery
        success = []
        errors = []
        failure = []
        skipped = []
        exceptions = []
        for game_dl in statuses:
            for download in game_dl['statuses']:
                identifier = f"{game_dl['name']}: {download['filename']}"
                if download['status'] == DownloadStatus.SUCCESS:
                    success.append(identifier)
                elif download['status'] == DownloadStatus.SKIP_EXISTING_FILE:
                    skipped.append(identifier)
                elif download['status'] in [DownloadStatus.NO_DOWNLOAD_ERROR, DownloadStatus.HTTP_ERROR]:
                    errors.append(identifier)
                elif download['status'] in [DownloadStatus.CORRUPTED, DownloadStatus.HASH_FAILURE]:
                    failure.append(identifier)
                elif isinstance(download['status'], Exception):
                    exceptions.append(identifier)
                    print(f"Traceback: {identifier}", file=stderr)
                    print_tb(download['status'].__traceback__, file=stderr)
                    print(f"{type(download['status']).__name__}: {download['status']}", file=stderr)
                else:
                    raise TypeError('Unknown status type')

        error_total = len(errors) + len(failure) + len(exceptions)
        if len(errors) > 0:
            logger.warning(f"See `errors.txt` for more information.")
        logger.info(f"File download summery: Downloaded({len(success)}) Skipped({len(skipped)}) Failed({error_total})")

        return bool(error_total < 1)
