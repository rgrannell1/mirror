"""Types describing camera storage, the files on it, and a removal plan."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass(frozen=True)
class CameraFile:
    """One media file on the camera, with the facts needed to rank and verify it."""

    path: Path
    relative: str
    size: int
    modified: datetime


@dataclass(frozen=True)
class SpaceReport:
    """How much space the card has, and how much the run must leave free."""

    total_bytes: int
    free_bytes: int
    target_free_bytes: int


@dataclass(frozen=True)
class FreePlan:
    """The files a run will remove, and where they go first."""

    files: tuple[CameraFile, ...]
    space: SpaceReport
    camera_dir: Path
    archive_path: Path | None
