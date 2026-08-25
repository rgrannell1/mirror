"""Copy a recent raw import into the managed library."""

from __future__ import annotations

from collections.abc import Generator
from typing import Any

from zahir import JobContext

from mirror.services.desktop import open_directory
from mirror.services.library_import import copy_recent_import


def copy_into_library(ctx: JobContext, input: dict) -> Generator[Any, Any, dict]:
    """Copy the Nth most recent raw folder into the managed media library and create Published/."""
    return copy_recent_import(input["title"], input["nth"])
    yield


def copy_open_nautilus(ctx: JobContext, input: dict) -> Generator[Any, Any, None]:
    """Open the destination directory in Nautilus."""
    open_directory(input["dest"])
    return None
    yield


def copy_workflow(ctx: JobContext, input: dict) -> Generator[Any, Any, None]:
    """Orchestrate copying a recent raw import into the managed library."""
    result = yield ctx.scope.copy_into_library({"title": input["title"], "nth": input["nth"]})
    yield ctx.scope.copy_open_nautilus({"dest": result["dest"]})
