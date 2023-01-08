import logging
import re
import json
import os
import urllib
import datetime
import shutil
import requests
from enum import Enum, auto


import itchiodl.utils


logger = logging.getLogger(__name__)


class DownloadStatus(Enum):
    SUCCESS = auto()
    SKIP_EXISTING_FILE = auto()
    CORRUPTED = auto()
    NO_DOWNLOAD_ERROR = auto()
    HTTP_ERROR = auto()
    HASH_FAILURE = auto()


class Game:
    """Representation of a game download"""

    def __init__(self, data):
        self.data = data["game"]
        self.name = self.data["title"]
        self.publisher = self.data["user"]["username"]
        self.link = self.data["url"]
        if "game_id" in data:
            self.id = data["id"]
            self.game_id = data["game_id"]
        else:
            self.id = False
            self.game_id = self.data["id"]

        matches = re.match(r"https://(.+)\.itch\.io/(.+)", self.link)
        self.game_slug = matches.group(2)
        self.publisher_slug = matches.group(1)

        self.files = []
        self.downloads = []

    def load_downloads(self, token):
        """Load all downloads for this game"""
        self.downloads = []
        if self.id:
            r = requests.get(
                f"https://api.itch.io/games/{self.game_id}/uploads?download_key_id={self.id}",
                headers={"Authorization": token},
            )
        else:
            r = requests.get(
                f"https://api.itch.io/games/{self.game_id}/uploads",
                headers={"Authorization": token},
            )
        j = r.json()
        for d in j["uploads"]:
            self.downloads.append(d)

    def download(self, token, platform):
        """Download a singular file"""
        logger.debug(f"Downloading {self.name}")

        self.load_downloads(token)

        if not os.path.exists(self.publisher_slug):
            os.mkdir(self.publisher_slug)

        if not os.path.exists(f"{self.publisher_slug}/{self.game_slug}"):
            os.mkdir(f"{self.publisher_slug}/{self.game_slug}")

        statuses = []
        for d in self.downloads:
            if (
                platform is not None
                and d["traits"]
                and f"p_{platform}" not in d["traits"]
            ):
                logger.info(f"Skipping {self.name} for platform {d['traits']}")
                continue
            status = self.do_download(d, token)
            statuses.append({
                "filename": d['filename'],
                "status": status
            })

        with open(f"{self.publisher_slug}/{self.game_slug}.json", "w") as f:
            json.dump(
                {
                    "name": self.name,
                    "publisher": self.publisher,
                    "link": self.link,
                    "itch_id": self.id,
                    "game_id": self.game_id,
                    "itch_data": self.data,
                },
                f,
                indent=2,
            )

        return statuses

    def do_download(self, d, token):
        """Download a single file, checking for existing files"""
        logger.debug(f"Downloading {d['filename']}")

        file = itchiodl.utils.clean_path(d["filename"] or d["display_name"] or d["id"])
        path = itchiodl.utils.clean_path(f"{self.publisher_slug}/{self.game_slug}")

        if os.path.exists(f"{path}/{file}"):
            logger.info(f"File Already Exists! {file}")
            if os.path.exists(f"{path}/{file}.md5"):

                with open(f"{path}/{file}.md5", "r") as f:
                    md5 = f.read().strip()

                    if md5 == d["md5_hash"]:
                        logger.info(f"Skipping {self.name} - {file}")
                        return DownloadStatus.SKIP_EXISTING_FILE
                    logger.warning(f"MD5 Mismatch! {file}")
            else:
                md5 = itchiodl.utils.md5sum(f"{path}/{file}")
                if md5 == d["md5_hash"]:
                    logger.info(f"Skipping {self.name} - {file}")

                    # Create checksum file
                    with open(f"{path}/{file}.md5", "w") as f:
                        f.write(d["md5_hash"])
                    return DownloadStatus.SKIP_EXISTING_FILE
                # Old Download or corrupted file?
                corrupted = False
                if corrupted:
                    os.remove(f"{path}/{file}")
                    return DownloadStatus.CORRUPTED

            if not os.path.exists(f"{path}/old"):
                os.mkdir(f"{path}/old")

            logger.info(f"Moving {file} to old/")
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d")
            logger.debug(timestamp)
            shutil.move(f"{path}/{file}", f"{path}/old/{timestamp}-{file}")

        # Get UUID
        r = requests.post(
            f"https://api.itch.io/games/{self.game_id}/download-sessions",
            headers={"Authorization": token},
        )
        j = r.json()

        # Download
        if self.id:
            url = (
                f"https://api.itch.io/uploads/{d['id']}/"
                + f"download?api_key={token}&download_key_id={self.id}&uuid={j['uuid']}"
            )
        else:
            url = (
                f"https://api.itch.io/uploads/{d['id']}/"
                + f"download?api_key={token}&uuid={j['uuid']}"
            )
        try:
            itchiodl.utils.download(url, path, self.name, file)
        except itchiodl.utils.NoDownloadError:
            logger.error("Http response is not a download, skipping")

            with open("errors.txt", "a") as f:
                f.write(
                    f""" Cannot download game/asset: {self.game_slug}
                    Publisher Name: {self.publisher_slug}
                    Path: {path}
                    File: {file}
                    Request URL: {url}
                    This request failed due to a missing response header
                    This game/asset has been skipped please download manually
                    ---------------------------------------------------------\n """
                )

            return DownloadStatus.NO_DOWNLOAD_ERROR
        except urllib.error.HTTPError as e:
            logger.error("This one has broken due to an HTTP error!!")

            with open("errors.txt", "a") as f:
                f.write(
                    f""" Cannot download game/asset: {self.game_slug}
                    Publisher Name: {self.publisher_slug}
                    Path: {path}
                    File: {file}
                    Request URL: {url}
                    Request Response Code: {e.code}
                    Error Reason: {e.reason}
                    This game/asset has been skipped please download manually
                    ---------------------------------------------------------\n """
                )

            return DownloadStatus.HTTP_ERROR

        # Verify
        if itchiodl.utils.md5sum(f"{path}/{file}") != d["md5_hash"]:
            logger.error(f"Failed to verify {file}")
            return DownloadStatus.HASH_FAILURE

        # Create checksum file
        with open(f"{path}/{file}.md5", "w") as f:
            f.write(d["md5_hash"])

        return DownloadStatus.SUCCESS
