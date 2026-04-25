"""Website build workflow: build source and publish D1 database remotely."""

from __future__ import annotations

import subprocess
from collections.abc import Generator
from typing import Any

from zahir import JobContext

from mirror.commons.config import WEBSITE_DIRECTORY


def build_source(ctx: JobContext, input: dict) -> Generator[Any, Any, None]:
    subprocess.run(["rs", "dev", "--build-only"], cwd=WEBSITE_DIRECTORY, check=True)
    return None
    yield


def publish_d1_remote(ctx: JobContext, input: dict) -> Generator[Any, Any, None]:
    subprocess.run(["rs", "deploy"], cwd=WEBSITE_DIRECTORY, check=True)
    return None
    yield


def build_website(ctx: JobContext, input: dict) -> Generator[Any, Any, None]:
    yield ctx.scope.build_source({})
    yield ctx.scope.publish_d1_remote({})
