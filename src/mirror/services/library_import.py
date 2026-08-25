"""Copy recent raw media imports into the managed library."""

import shutil
from datetime import date
from pathlib import Path

from mirror.commons.config import PHOTO_DIRECTORY, RAW_MEDIA_DIRECTORY


def find_nth_raw_folder(nth: int) -> Path:
    """Return the Nth most recent raw import directory."""
    raw_root = Path(RAW_MEDIA_DIRECTORY)
    if not raw_root.exists():
        raise FileNotFoundError(f"Raw media directory not found: {raw_root}")

    subdirs = sorted(
        [entry for entry in raw_root.iterdir() if entry.is_dir()],
        key=lambda entry: entry.stat().st_mtime,
        reverse=True,
    )
    if not subdirs:
        raise FileNotFoundError(f"No folders found under {raw_root}")
    if nth > len(subdirs):
        found = f"only {len(subdirs)} folder(s) exist under {raw_root}"
        raise FileNotFoundError(f"Requested import #{nth} but {found}")
    return subdirs[nth - 1]


def copy_recent_import(title: str, nth: int) -> dict[str, str]:
    """Copy a raw import into the current year's managed library."""
    source = find_nth_raw_folder(nth)
    destination = Path(PHOTO_DIRECTORY) / str(date.today().year) / title
    shutil.copytree(source, destination, dirs_exist_ok=True)
    (destination / "Published").mkdir(exist_ok=True)
    return {"dest": str(destination), "src": str(source)}
