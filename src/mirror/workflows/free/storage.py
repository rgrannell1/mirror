"""Read the camera's storage: its mount, its free space, and the media on it."""

from __future__ import annotations

import math
import os
from datetime import datetime
from pathlib import Path

from mirror.commons.constants import BYTE_UNITS, BYTES_PER_UNIT, SUPPORTED_MEDIA_EXTENSIONS
from mirror.workflows.free.free_types import CameraFile, SpaceReport


def accepts_deletes(camera_dir: Path) -> bool:
    """Say whether the card can lose files: not a read-only mount, and writable to us."""
    if os.statvfs(camera_dir).f_flag & os.ST_RDONLY:
        return False
    return os.access(camera_dir, os.W_OK)


def resolve_camera_dir(camera: str) -> Path:
    """Return the camera directory, raising when the card is absent or cannot lose files."""
    camera_dir = Path(camera)
    if not camera_dir.is_dir():
        raise FileNotFoundError(f"Camera not mounted: {camera}")

    if not accepts_deletes(camera_dir):
        raise PermissionError(
            f"Camera is mounted read-only: {camera}. Nothing can be deleted from it."
            " The device reports the card as write-protected. Check the card's lock"
            " switch, or read the card in a USB card reader instead of the camera"
        )

    return camera_dir


def read_space(camera_dir: Path, percent: float) -> SpaceReport:
    """Measure the card's capacity and free space, and the target free space."""
    stats = os.statvfs(camera_dir)
    total_bytes = stats.f_blocks * stats.f_frsize
    free_bytes = stats.f_bavail * stats.f_frsize
    target = math.ceil(total_bytes * percent / 100)
    return SpaceReport(total_bytes=total_bytes, free_bytes=free_bytes, target_free_bytes=target)


def bytes_needed(space: SpaceReport) -> int:
    """Return the bytes still to free, or zero when the target is already met."""
    return max(0, space.target_free_bytes - space.free_bytes)


def read_camera_file(path: Path, camera_dir: Path) -> CameraFile:
    """Describe one media file relative to the camera directory."""
    stats = path.stat()
    return CameraFile(
        path=path,
        relative=str(path.relative_to(camera_dir)),
        size=stats.st_size,
        modified=datetime.fromtimestamp(stats.st_mtime),
    )


def to_entry(media: CameraFile) -> dict:
    """Reduce a camera file to the primitives a job input can carry."""
    return {
        "path": str(media.path),
        "relative": media.relative,
        "size": media.size,
        "modified": media.modified.timestamp(),
    }


def from_entry(entry: dict) -> CameraFile:
    """Rebuild a camera file from a job input entry."""
    return CameraFile(
        path=Path(entry["path"]),
        relative=entry["relative"],
        size=entry["size"],
        modified=datetime.fromtimestamp(entry["modified"]),
    )


def list_camera_files(camera_dir: Path) -> list[CameraFile]:
    """Return every supported media file under the camera directory."""
    found = camera_dir.rglob("*")
    media = (path for path in found if path.suffix in SUPPORTED_MEDIA_EXTENSIONS and path.is_file())
    return [read_camera_file(path, camera_dir) for path in media]


def format_bytes(count: int) -> str:
    """Render a byte count in the largest unit that keeps it above one."""
    size = float(count)
    for unit in BYTE_UNITS[:-1]:
        if abs(size) < BYTES_PER_UNIT:
            return f"{size:.1f} {unit}"
        size /= BYTES_PER_UNIT
    return f"{size:.1f} {BYTE_UNITS[-1]}"


def format_share(part: int, whole: int) -> str:
    """Render a byte count as a percentage of a whole."""
    if whole <= 0:
        return "0.0%"
    return f"{100 * part / whole:.1f}%"
