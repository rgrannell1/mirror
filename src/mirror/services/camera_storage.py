"""Read the camera's storage: its mount, its free space, and the media on it."""

from __future__ import annotations

import math
import os
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path
from typing import Any

import psutil

from mirror.commons.constants import (
    BYTE_UNITS,
    BYTES_PER_UNIT,
    SUPPORTED_MEDIA_EXTENSIONS,
    SYS_BLOCK_DIRECTORY,
)
from mirror.services.camera_types import CameraFile, SpaceReport


def accepts_deletes(camera_dir: Path) -> bool:
    """Say whether the card can lose files: not a read-only mount, and writable to us."""
    if os.statvfs(camera_dir).f_flag & os.ST_RDONLY:
        return False
    return os.access(camera_dir, os.W_OK)


def is_removable_device(device: str, sys_block_dir: Path = SYS_BLOCK_DIRECTORY) -> bool:
    """Say whether Linux marks the device or its parent disk as removable."""
    device_dir = sys_block_dir / Path(device).name
    if not device_dir.exists():
        return False

    resolved = device_dir.resolve()
    for candidate in (resolved, resolved.parent):
        removable = candidate / "removable"
        if removable.is_file():
            return removable.read_text().strip() == "1"
    return False


def read_partitions(partitions: Sequence[Any] | None) -> Sequence[Any]:
    """Return supplied partitions, or read the current mounted partitions."""
    return partitions if partitions is not None else psutil.disk_partitions()


def mount_depth(partition: Any) -> int:
    """Return a mount path depth for selecting the closest mounted partition."""
    return len(Path(partition.mountpoint).parts)


def find_partition(camera_dir: Path, partitions: Sequence[Any]) -> Any | None:
    """Find the closest mounted partition containing the camera directory."""
    resolved = camera_dir.resolve()
    matches = [
        partition
        for partition in partitions
        if resolved.is_relative_to(Path(partition.mountpoint).resolve())
    ]
    return max(matches, key=mount_depth) if matches else None


def detect_camera_dir(partitions: Sequence[Any] | None = None) -> Path:
    """Find the sole mounted removable partition that contains a DCIM directory."""
    mounted = read_partitions(partitions)
    candidates = [
        Path(partition.mountpoint) / "DCIM"
        for partition in mounted
        if is_removable_device(partition.device) and (Path(partition.mountpoint) / "DCIM").is_dir()
    ]
    if not candidates:
        raise FileNotFoundError("No mounted removable card with a DCIM directory found")
    if len(candidates) > 1:
        raise RuntimeError("More than one removable card has a DCIM directory. Use --camera")
    return candidates[0]


def require_removable_device(camera_dir: Path, partitions: Sequence[Any] | None = None) -> None:
    """Reject a camera directory that does not belong to removable storage."""
    partition = find_partition(camera_dir, read_partitions(partitions))
    if partition is None or not is_removable_device(partition.device):
        raise PermissionError(f"Refusing camera path on non-removable storage: {camera_dir}")


def resolve_camera_dir(camera: str | None) -> Path:
    """Return the camera directory, raising when the card is absent or cannot lose files."""
    camera_dir = Path(camera) if camera is not None else detect_camera_dir()
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


def delete_camera_file(path: str) -> None:
    """Delete one camera file."""
    Path(path).unlink()


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
