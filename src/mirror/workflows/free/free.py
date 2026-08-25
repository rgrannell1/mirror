"""Zahir jobs that free camera space: archive, verify, then delete.

Archiving is one gzip stream, so one job writes it and fires a semaphore per
file. Lightweight proxy jobs wait on those semaphores, so the progress tree
shows a job per file. Deleting fans out for real.

Cancelling is safe at every point. The archive is written under a .partial
name and only renamed once verified, so a cancelled run never leaves a
whole-looking archive, and never deletes a file that is not already in one.
"""

from __future__ import annotations

from collections.abc import Generator
from pathlib import Path
from typing import Any

from zahir import JobContext, await_all, concurrency_dependency, semaphore_dependency
from zahir.core.commons.constants import DependencyState
from zahir.core.effects import ESetState

from mirror.services.camera_archive import (
    find_unverified,
    partial_path,
    promote_archive,
    write_archive,
)
from mirror.services.camera_storage import delete_camera_file, format_bytes, from_entry
from mirror.workflows.output import workflow_output

# Limit concurrent deletes so one run cannot saturate the card's USB bus.
FREE_DELETE_LIMIT = "free_delete_limit"

# At most this many files are unlinked at once.
FREE_DELETE_CONCURRENCY = 8

# Semaphore name prefix signalling that file N reached the archive.
FREE_ARCHIVE_SEMAPHORE = "free_archive"


def free_archive_media(ctx: JobContext, input: dict) -> Generator[Any, Any, dict]:
    """Write every planned file into the partial archive, signalling one semaphore per file."""
    files = tuple(from_entry(entry) for entry in input["files"])
    target = partial_path(Path(input["archive_path"]))

    for idx in write_archive(target, files):
        yield ESetState(name=f"{FREE_ARCHIVE_SEMAPHORE}_{idx}", value=DependencyState.SATISFIED)

    return {"archived": len(files)}
    yield


def free_archive_file(ctx: JobContext, input: dict) -> Generator[Any, Any, None]:
    """Proxy job that completes when one file reaches the archive."""
    yield from semaphore_dependency(f"{FREE_ARCHIVE_SEMAPHORE}_{input['idx']}")
    return None
    yield


def free_verify_archive(ctx: JobContext, input: dict) -> Generator[Any, Any, dict]:
    """Check the archive holds every file at its expected size, then give it its final name."""
    files = tuple(from_entry(entry) for entry in input["files"])
    archive_path = Path(input["archive_path"])

    unverified = find_unverified(partial_path(archive_path), files)
    if unverified:
        named = ", ".join(media.relative for media in unverified[:5])
        raise RuntimeError(
            f"{len(unverified)} files are missing from the archive ({named})."
            " Nothing was deleted."
        )

    promote_archive(archive_path)
    return {"verified": len(files)}
    yield


def free_delete_file(ctx: JobContext, input: dict) -> Generator[Any, Any, dict]:
    """Delete one verified file from the camera, reporting rather than raising on failure."""
    yield from concurrency_dependency(FREE_DELETE_LIMIT, limit=FREE_DELETE_CONCURRENCY)

    try:
        delete_camera_file(input["path"])
    except OSError as err:
        return {"freed": 0, "error": f"{input['relative']}: {err}"}

    return {"freed": input["size"], "error": None}
    yield


def summarise_deletes(results: list[dict]) -> dict:
    """Total the bytes freed and collect any files that would not delete."""
    freed = sum(result["freed"] for result in results)
    errors = [result["error"] for result in results if result["error"]]
    deleted = sum(1 for result in results if result["error"] is None)
    return {"deleted": deleted, "freed": freed, "errors": errors}


def free_workflow(ctx: JobContext, input: dict) -> Generator[Any, Any, dict]:
    """Archive the planned files, verify them, then delete them from the camera."""
    entries = input["files"]
    archive_path = input["archive_path"]

    if archive_path:
        archive_input = {"files": entries, "archive_path": archive_path}
        yield await_all([
            ctx.scope.free_archive_media(archive_input),
            *[ctx.scope.free_archive_file({"idx": idx}) for idx in range(len(entries))],
        ])
        yield ctx.scope.free_verify_archive(archive_input)

    results = yield await_all([ctx.scope.free_delete_file(entry) for entry in entries])

    summary = summarise_deletes(results)
    yield workflow_output(
        f"removed {summary['deleted']} files, freeing {format_bytes(summary['freed'])}"
    )
    for error in summary["errors"]:
        yield workflow_output(f"could not delete {error}")

    return summary
    yield
