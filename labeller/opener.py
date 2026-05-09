"""Resolve a CDN thumbnail URL to its local file path and open it."""

import subprocess
from pathlib import Path

from mirror.services.database.facade import SqliteDatabase

DB_PATH = Path.home() / "media.db"


def fpath_for_url(url: str) -> str | None:
    """Look up the local file path for a CDN URL, or return None if not found."""
    db = SqliteDatabase(str(DB_PATH))
    return db.encoded_photos_table().fpath_from_url(url)


def webp_url_for_url(url: str) -> str:
    """Return the thumbnail_webp CDN URL for the photo at url, falling back to url if not found."""
    db = SqliteDatabase(str(DB_PATH))
    fpath = db.encoded_photos_table().fpath_from_url(url)
    if fpath is None:
        return url
    for enc in db.encoded_photos_table().list_for_file(fpath):
        if enc.role == "thumbnail_webp":
            return enc.url
    return url


def open_in_viewer(fpath: str) -> None:
    """Open a file in the OS default viewer (non-blocking)."""
    subprocess.Popen(["xdg-open", fpath])
