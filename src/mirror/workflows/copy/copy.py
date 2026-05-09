"""Copies the most recent raw import folder into the managed library under PHOTO_DIRECTORY/<year>/<title>/."""

from __future__ import annotations

import shutil
import subprocess
from collections.abc import Generator
from datetime import date
from pathlib import Path
from typing import Any

from zahir import JobContext

from mirror.commons.config import PHOTO_DIRECTORY, RAW_MEDIA_DIRECTORY


def find_nth_raw_folder(nth: int) -> Path:
    """Return the Nth most recently modified directory under RAW_MEDIA_DIRECTORY."""
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
        raise FileNotFoundError(f"Requested import #{nth} but only {len(subdirs)} folder(s) exist under {raw_root}")

    return subdirs[nth - 1]


def resolve_dest(title: str) -> Path:
    """Return the destination path PHOTO_DIRECTORY/<current-year>/<title>."""
    year = date.today().year
    return Path(PHOTO_DIRECTORY) / str(year) / title


def copy_into_library(ctx: JobContext, input: dict) -> Generator[Any, Any, dict]:
    """Copy the Nth most recent raw folder into the managed media library and create Published/."""
    src = find_nth_raw_folder(input["nth"])
    dest = resolve_dest(input["title"])

    shutil.copytree(src, dest, dirs_exist_ok=True)

    published = dest / "Published"
    published.mkdir(exist_ok=True)

    return {"dest": str(dest), "src": str(src)}
    yield


def copy_open_nautilus(ctx: JobContext, input: dict) -> Generator[Any, Any, None]:
    """Open the destination directory in Nautilus."""
    subprocess.Popen(["nautilus", input["dest"]])
    return None
    yield


def copy_workflow(ctx: JobContext, input: dict) -> Generator[Any, Any, None]:
    """Orchestrate copying a recent raw import into the managed library."""
    result = yield ctx.scope.copy_into_library({"title": input["title"], "nth": input["nth"]})
    yield ctx.scope.copy_open_nautilus({"dest": result["dest"]})
