"""Top-level class for interacting with the nested photo of folders"""

import os
from typing import Iterator

from src.album import Album


class MediaVault:
    """Represents a nested folder of photos and videos."""

    dpath: str
    skipped: set[str]

    def __init__(self, dpath: str):
        self.dpath = dpath
        self.skipped = {"Published", ".vscode", ".git", ".dtrash"}

    def albums(self) -> Iterator[Album]:
        """Get all albums in the media vault"""
        for dpath, dirs, _ in os.walk(self.dpath):
            basename = os.path.basename(dpath)

            dirs[:] = [dir for dir in dirs if dir not in self.skipped]

            skipped = any(basename == skipped for skipped in self.skipped)
            if skipped:
                continue

            album = Album(dpath)
            if album.published():
                yield album
