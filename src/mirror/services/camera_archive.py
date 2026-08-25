"""Archive camera media into a tar.gz, then prove every file landed in it."""

from __future__ import annotations

import tarfile
from collections.abc import Iterator
from datetime import date
from pathlib import Path

from mirror.services.camera_types import CameraFile

# Extension marking an archive still being written. A cancelled run leaves one behind.
PARTIAL_SUFFIX = ".partial"


def build_archive_path(directory: Path, first: date, last: date) -> Path:
    """Name the archive by its date range, adding a suffix rather than overwriting."""
    directory.mkdir(parents=True, exist_ok=True)
    stem = f"{first.isoformat()}_{last.isoformat()}"

    candidate = directory / f"{stem}.tar.gz"
    attempt = 2
    while candidate.exists():
        candidate = directory / f"{stem}-{attempt}.tar.gz"
        attempt += 1

    return candidate


def partial_path(archive_path: Path) -> Path:
    """Name the half-written archive. A cancelled run leaves this, never a whole-looking one."""
    return archive_path.with_name(archive_path.name + PARTIAL_SUFFIX)


def promote_archive(archive_path: Path) -> None:
    """Rename a verified partial archive to its final name."""
    partial_path(archive_path).rename(archive_path)


def write_archive(archive_path: Path, files: tuple[CameraFile, ...]) -> Iterator[int]:
    """Write each planned file into the archive, yielding its index once it is stored.

    This is a generator, so nothing is written until it is consumed. Callers that
    want the whole archive must drain it. Closing it early shuts the archive
    cleanly, leaving a partial file rather than a corrupt one.
    """
    with tarfile.open(archive_path, "w:gz") as archive:
        for idx, media in enumerate(files):
            archive.add(media.path, arcname=media.relative)
            yield idx


def read_archive_sizes(archive_path: Path) -> dict[str, int]:
    """Return the size of each regular file stored in the archive."""
    with tarfile.open(archive_path, "r:gz") as archive:
        return {entry.name: entry.size for entry in archive.getmembers() if entry.isfile()}


def find_unverified(archive_path: Path, files: tuple[CameraFile, ...]) -> list[CameraFile]:
    """Return the planned files the archive does not hold at the expected size."""
    stored = read_archive_sizes(archive_path)
    return [media for media in files if stored.get(media.relative) != media.size]
