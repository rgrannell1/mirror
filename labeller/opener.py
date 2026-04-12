"""Resolve a CDN thumbnail URL to its local file path and open it."""

import subprocess
from pathlib import Path

from mirror.services.database.facade import SqliteDatabase

DB_PATH = Path.home() / "media.db"


def fpath_for_url(url: str) -> str | None:
    """Look up the local file path for a CDN URL, or return None if not found."""
    db = SqliteDatabase(str(DB_PATH))
    return db.encoded_photos_table().fpath_from_url(url)


def open_in_viewer(fpath: str) -> None:
    """Open a file in the OS default viewer (non-blocking)."""
    subprocess.Popen(["xdg-open", fpath])
