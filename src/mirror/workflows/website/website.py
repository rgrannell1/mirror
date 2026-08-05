"""Website build workflow: build source and publish D1 database remotely."""

from __future__ import annotations

import subprocess
from collections.abc import Generator
from typing import Any

from zahir import JobContext

from mirror.commons.config import WEBSITE_DIRECTORY
from mirror.commons.constants import BUILD_OUTPUT_TAIL_LINES
from mirror.commons.exceptions import WebsiteBuildError
from mirror.services.github import publish_manifest


def run_website_step(command: list[str]) -> None:
    """Run a website build command. On failure, raise with the output tail."""
    result = subprocess.run(command, cwd=WEBSITE_DIRECTORY, capture_output=True, text=True)
    if result.returncode == 0:
        return

    lines = (result.stdout + result.stderr).splitlines()
    tail = "\n".join(lines[-BUILD_OUTPUT_TAIL_LINES:])
    raise WebsiteBuildError(f"`{' '.join(command)}` exited {result.returncode}:\n{tail}")


def build_source(ctx: JobContext, input: dict) -> Generator[Any, Any, None]:
    run_website_step(["rs", "dev", "--build-only"])
    return None
    yield


def run_integration_tests(ctx: JobContext, input: dict) -> Generator[Any, Any, None]:
    run_website_step(["rs", "integration_test", "--quiet"])
    return None
    yield


def publish_d1_remote(ctx: JobContext, input: dict) -> Generator[Any, Any, None]:
    run_website_step(["rs", "deploy"])
    return None
    yield


def publish_github(ctx: JobContext, input: dict) -> Generator[Any, Any, str | None]:
    """Publish the manifest and build artifacts from the local website repo."""
    return publish_manifest()
    yield


def build_website(ctx: JobContext, input: dict) -> Generator[Any, Any, None]:
    yield ctx.scope.build_source({})
    yield ctx.scope.publish_d1_remote({})
