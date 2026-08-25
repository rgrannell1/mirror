"""Fetch media from a connected camera, cluster it with badger, and open the result."""

from __future__ import annotations

import json
from collections.abc import Generator
from typing import Any

from zahir import JobContext, await_all, concurrency_dependency, semaphore_dependency
from zahir.core.commons.constants import DependencyState
from zahir.core.effects import ESetState

from mirror.services.badger import check_badger_exit, start_badger
from mirror.services.camera_import import copy_camera_file, parse_date_range, prepare_camera_import
from mirror.services.desktop import open_directory

# Limit concurrent USB reads to avoid saturating the bus
_COPY_LIMIT = "fetch_copy_limit"


def signal_range(name_prefix: str, start: int, end: int) -> Generator[Any, Any, None]:
    """Yield ESetState for indices [start, end), satisfying each semaphore."""
    for idx in range(start, end):
        yield ESetState(name=f"{name_prefix}_{idx}", value=DependencyState.SATISFIED)


# --- zahir specs ---


def fetch_resolve_dates(ctx: JobContext, input: dict) -> Generator[Any, Any, dict]:
    """Parse --from and --to strings into ISO date strings."""
    from_date, to_date = parse_date_range(input["from_str"], input["to_str"])
    return {"from_date": from_date.isoformat(), "to_date": to_date.isoformat()}
    yield


def fetch_find_filtered(ctx: JobContext, input: dict) -> Generator[Any, Any, dict]:
    """Find camera files matching the date range and create the staging directory."""
    return prepare_camera_import(input["camera"], input["from_date"], input["to_date"])
    yield


def fetch_copy_file(ctx: JobContext, input: dict) -> Generator[Any, Any, None]:
    """Copy a single file from the camera to the staging directory."""
    yield from concurrency_dependency(_COPY_LIMIT, limit=8)
    copy_camera_file(input["src"], input["dest"])
    return None
    yield


def parse_badger_progress(line: str) -> dict | None:
    """Parse one JSON progress line from badger, returning None if not valid JSON."""
    try:
        return json.loads(line.strip())
    except json.JSONDecodeError:
        return None


def stream_badger_progress(proc) -> Generator[Any, Any, dict]:
    """Fire semaphores as badger reports progress; return the final progress counts."""
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

    return last_progress


def fetch_run_badger(ctx: JobContext, input: dict) -> Generator[Any, Any, dict]:
    """Run badger, firing one semaphore per file as each is clustered."""
    process = start_badger(input["dest"])

    last_progress = yield from stream_badger_progress(process)

    process.wait()
    check_badger_exit(process)

    # Fallback: satisfy any semaphores not yet signalled (e.g. no progress output)
    prev_photos = last_progress.get("photos_done", 0)
    prev_videos = last_progress.get("videos_done", 0)
    prev_raws = last_progress.get("raws_done", 0)

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
    open_directory(input["dest"])
    return None
    yield


def fetch_workflow(ctx: JobContext, input: dict) -> Generator[Any, Any, None]:
    """Orchestrate the full camera import flow."""
    date_input = {"from_str": input["from_str"], "to_str": input["to_str"]}
    dates = yield ctx.scope.fetch_resolve_dates(date_input)

    found = yield ctx.scope.fetch_find_filtered({
        "from_date": dates["from_date"],
        "to_date": dates["to_date"],
        "camera": input["camera"],
    })

    dest = found["dest"]

    yield await_all([
        ctx.scope.fetch_copy_file({"src": src, "dest": dest}) for src in found["filtered"]
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
