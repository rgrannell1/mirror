"""Fetches photos and videos from a connected camera, clusters them with badger, and opens the result."""

from __future__ import annotations

import glob
import json
import shutil
import subprocess
from collections.abc import Generator
from datetime import date, datetime
from pathlib import Path
from typing import Any

import dateparser
from zahir import ESetSemaphore, JobContext, await_all, concurrency_dependency, semaphore_dependency

from mirror.commons.config import BADGER_PATH, RAW_MEDIA_DIRECTORY
from mirror.commons.constants import SUPPORTED_IMAGE_EXTENSIONS

SUPPORTED_VIDEO_EXTENSIONS = (".mp4", ".MP4", ".mov", ".MOV")
SUPPORTED_RAW_EXTENSIONS = (".rw2", ".RW2", ".raw", ".RAW", ".dng", ".DNG")
SUPPORTED_EXTENSIONS = (
    frozenset(SUPPORTED_IMAGE_EXTENSIONS) | frozenset(SUPPORTED_VIDEO_EXTENSIONS) | frozenset(SUPPORTED_RAW_EXTENSIONS)
)

_PHOTO_EXTS = frozenset(SUPPORTED_IMAGE_EXTENSIONS)
_VIDEO_EXTS = frozenset(SUPPORTED_VIDEO_EXTENSIONS)

# Limit concurrent USB reads to avoid saturating the bus
_COPY_LIMIT = "fetch_copy_limit"


def parse_date_range(raw_from: str, raw_to: str) -> tuple[date, date]:
    """Parse two human-readable date strings into date objects."""
    from_dt = dateparser.parse(raw_from)
    if from_dt is None:
        raise ValueError(f"Could not parse --from date: {raw_from!r}")

    to_dt = dateparser.parse(raw_to)
    if to_dt is None:
        raise ValueError(f"Could not parse --to date: {raw_to!r}")

    return from_dt.date(), to_dt.date()


def find_camera_files(dcim_dir: str) -> list[Path]:
    """Return all supported media files found recursively under dcim_dir."""
    dcim_path = Path(dcim_dir)
    if not dcim_path.exists():
        raise FileNotFoundError(f"Camera DCIM directory not found: {dcim_dir}")

    all_files = glob.glob(str(dcim_path / "**" / "*"), recursive=True)
    return [Path(fpath) for fpath in all_files if Path(fpath).suffix in SUPPORTED_EXTENSIONS and Path(fpath).is_file()]


def file_date(path: Path) -> date:
    """Return the creation date of a media file from mtime."""
    return datetime.fromtimestamp(path.stat().st_mtime).date()


def filter_files_by_date(files: list[Path], from_date: date, to_date: date) -> list[Path]:
    """Keep only files whose creation date falls within [from_date, to_date] inclusive."""
    return [fpath for fpath in files if from_date <= file_date(fpath) <= to_date]


def build_dest_dir(from_date: date, to_date: date) -> Path:
    """Create and return ~/RawMedia/<from_date>_<to_date>/."""
    dest = Path(RAW_MEDIA_DIRECTORY) / f"{from_date}_{to_date}"
    dest.mkdir(parents=True, exist_ok=True)
    return dest


def count_by_type(files: list[Path]) -> tuple[int, int, int]:
    """Return (photo_count, video_count, raw_count) for a list of media files."""
    photos = sum(1 for fpath in files if fpath.suffix in _PHOTO_EXTS)
    videos = sum(1 for fpath in files if fpath.suffix in _VIDEO_EXTS)
    raws = len(files) - photos - videos
    return photos, videos, raws


def copy_single_file(src: Path, dest_root: Path) -> None:
    """Copy one file flat into dest_root, dropping any camera subfolder structure."""
    shutil.copy2(src, dest_root / src.name)


def signal_range(name_prefix: str, start: int, end: int) -> Generator[Any, Any, None]:
    """Yield ESetSemaphore for indices [start, end), satisfying each."""
    for idx in range(start, end):
        yield ESetSemaphore(f"{name_prefix}_{idx}", "satisfied")


# --- zahir specs ---


def fetch_resolve_dates(ctx: JobContext, input: dict) -> Generator[Any, Any, dict]:
    """Parse --from and --to strings into ISO date strings."""
    from_date, to_date = parse_date_range(input["from_str"], input["to_str"])
    return {"from_date": from_date.isoformat(), "to_date": to_date.isoformat()}
    yield


def fetch_find_filtered(ctx: JobContext, input: dict) -> Generator[Any, Any, dict]:
    """Find camera files matching the date range and create the staging directory."""
    from_date = date.fromisoformat(input["from_date"])
    to_date = date.fromisoformat(input["to_date"])

    files = find_camera_files(input["camera"])
    filtered = filter_files_by_date(files, from_date, to_date)

    if not filtered:
        raise ValueError(f"No files found between {from_date} and {to_date}")

    photo_count, video_count, raw_count = count_by_type(filtered)
    dest = build_dest_dir(from_date, to_date)

    return {
        "filtered": [str(fpath) for fpath in filtered],
        "dest": str(dest),
        "photo_count": photo_count,
        "video_count": video_count,
        "raw_count": raw_count,
    }
    yield


def fetch_copy_file(ctx: JobContext, input: dict) -> Generator[Any, Any, None]:
    """Copy a single file from the camera to the staging directory."""
    yield from concurrency_dependency(_COPY_LIMIT, limit=8)
    copy_single_file(Path(input["src"]), Path(input["dest"]))
    return None
    yield


def parse_badger_progress(line: str) -> dict | None:
    """Parse one JSON progress line from badger, returning None if not valid JSON."""
    try:
        return json.loads(line.strip())
    except json.JSONDecodeError:
        return None


def fetch_run_badger(ctx: JobContext, input: dict) -> Generator[Any, Any, dict]:
    """Run badger, firing one semaphore per file as each is clustered."""
    dest = input["dest"]
    src_glob = str(Path(dest) / "**" / "*")

    proc = subprocess.Popen(
        [BADGER_PATH, "cluster", "--from", src_glob, "--to", dest, "--yes", "--json-progress"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    prev_photos = prev_videos = prev_raws = 0
    last_progress: dict = {}

    for line in proc.stdout:  # type: ignore[union-attr]
        parsed = parse_badger_progress(line)
        if parsed is None:
            continue

        yield from signal_range("badger_photo", prev_photos, parsed["photos_done"])
        yield from signal_range("badger_video", prev_videos, parsed["videos_done"])
        yield from signal_range("badger_raw", prev_raws, parsed["raws_done"])

        prev_photos = parsed["photos_done"]
        prev_videos = parsed["videos_done"]
        prev_raws = parsed["raws_done"]
        last_progress = parsed

    proc.wait()
    if proc.returncode != 0:
        stderr_out = proc.stderr.read() if proc.stderr else ""  # type: ignore[union-attr]
        raise RuntimeError(f"badger exited {proc.returncode}: {stderr_out.strip()}")

    # Fallback: satisfy any semaphores not yet signalled (e.g. no progress output)
    yield from signal_range("badger_photo", prev_photos, input["photo_count"])
    yield from signal_range("badger_video", prev_videos, input["video_count"])
    yield from signal_range("badger_raw", prev_raws, input["raw_count"])

    return last_progress
    yield


def fetch_photo_clustering(ctx: JobContext, input: dict) -> Generator[Any, Any, None]:
    """Proxy job that completes when badger clusters one photo."""
    yield from semaphore_dependency(f"badger_photo_{input['idx']}")
    return None
    yield


def fetch_media_clustering(ctx: JobContext, input: dict) -> Generator[Any, Any, None]:
    """Proxy job that completes when badger clusters one video."""
    yield from semaphore_dependency(f"badger_video_{input['idx']}")
    return None
    yield


def fetch_raw_clustering(ctx: JobContext, input: dict) -> Generator[Any, Any, None]:
    """Proxy job that completes when badger clusters one raw file."""
    yield from semaphore_dependency(f"badger_raw_{input['idx']}")
    return None
    yield


def fetch_open_nautilus(ctx: JobContext, input: dict) -> Generator[Any, Any, None]:
    """Open the staging directory in Nautilus."""
    subprocess.Popen(["nautilus", input["dest"]])
    return None
    yield


def fetch_workflow(ctx: JobContext, input: dict) -> Generator[Any, Any, None]:
    """Orchestrate the full camera import flow."""
    dates = yield ctx.scope.fetch_resolve_dates({"from_str": input["from_str"], "to_str": input["to_str"]})

    found = yield ctx.scope.fetch_find_filtered({
        "from_date": dates["from_date"],
        "to_date": dates["to_date"],
        "camera": input["camera"],
    })

    dest = found["dest"]

    yield await_all([
        ctx.scope.fetch_copy_file({"src": src, "dest": dest})
        for src in found["filtered"]
    ])

    badger_input = {
        "dest": dest,
        "photo_count": found["photo_count"],
        "video_count": found["video_count"],
        "raw_count": found["raw_count"],
    }

    yield await_all([
        ctx.scope.fetch_run_badger(badger_input),
        *[ctx.scope.fetch_photo_clustering({"idx": idx}) for idx in range(found["photo_count"])],
        *[ctx.scope.fetch_media_clustering({"idx": idx}) for idx in range(found["video_count"])],
        *[ctx.scope.fetch_raw_clustering({"idx": idx}) for idx in range(found["raw_count"])],
    ])

    yield ctx.scope.fetch_open_nautilus({"dest": dest})
