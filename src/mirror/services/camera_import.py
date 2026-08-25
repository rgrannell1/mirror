"""Find and copy camera media into a raw import directory."""

import glob
import shutil
from datetime import date, datetime
from pathlib import Path

import dateparser

from mirror.commons.config import RAW_MEDIA_DIRECTORY
from mirror.commons.constants import (
    SUPPORTED_IMAGE_EXTENSIONS,
    SUPPORTED_MEDIA_EXTENSIONS,
    SUPPORTED_VIDEO_EXTENSIONS,
)


def parse_date_range(raw_from: str, raw_to: str) -> tuple[date, date]:
    """Parse two human-readable dates."""
    from_datetime = dateparser.parse(raw_from)
    if from_datetime is None:
        raise ValueError(f"Could not parse --from date: {raw_from!r}")
    to_datetime = dateparser.parse(raw_to)
    if to_datetime is None:
        raise ValueError(f"Could not parse --to date: {raw_to!r}")
    return from_datetime.date(), to_datetime.date()


def find_camera_files(camera_dir: str) -> list[Path]:
    """Return supported files below a camera directory."""
    camera_path = Path(camera_dir)
    if not camera_path.exists():
        raise FileNotFoundError(f"Camera DCIM directory not found: {camera_dir}")
    paths = (Path(path) for path in glob.glob(str(camera_path / "**" / "*"), recursive=True))
    return [path for path in paths if path.suffix in SUPPORTED_MEDIA_EXTENSIONS and path.is_file()]


def prepare_camera_import(camera_dir: str, from_iso: str, to_iso: str) -> dict:
    """Find dated camera files and create their raw import directory."""
    from_date = date.fromisoformat(from_iso)
    to_date = date.fromisoformat(to_iso)
    files = find_camera_files(camera_dir)
    filtered = [
        path
        for path in files
        if from_date <= datetime.fromtimestamp(path.stat().st_mtime).date() <= to_date
    ]
    if not filtered:
        raise ValueError(f"No files found between {from_date} and {to_date}")

    photo_extensions = frozenset(SUPPORTED_IMAGE_EXTENSIONS)
    video_extensions = frozenset(SUPPORTED_VIDEO_EXTENSIONS)
    photo_count = sum(path.suffix in photo_extensions for path in filtered)
    video_count = sum(path.suffix in video_extensions for path in filtered)
    destination = Path(RAW_MEDIA_DIRECTORY) / f"{from_date}_{to_date}"
    destination.mkdir(parents=True, exist_ok=True)
    return {
        "filtered": [str(path) for path in filtered],
        "dest": str(destination),
        "photo_count": photo_count,
        "video_count": video_count,
        "raw_count": len(filtered) - photo_count - video_count,
    }


def copy_camera_file(source: str, destination: str) -> None:
    """Copy one camera file into a flat raw import directory."""
    source_path = Path(source)
    shutil.copy2(source_path, Path(destination) / source_path.name)
