"""Website build workflow: build source and publish D1 database remotely."""

from __future__ import annotations

import subprocess
import tempfile
from collections.abc import Generator
from typing import Any

from zahir import JobContext

from mirror.commons.config import WEBSITE_DIRECTORY
from mirror.services.github import publish_manifest


def build_source(ctx: JobContext, input: dict) -> Generator[Any, Any, None]:
    subprocess.run(["rs", "dev", "--build-only"], cwd=WEBSITE_DIRECTORY, check=True)
    return None
    yield


def run_integration_tests(ctx: JobContext, input: dict) -> Generator[Any, Any, None]:
    subprocess.run(["rs", "integration_test", "--quiet"], cwd=WEBSITE_DIRECTORY, check=True)
    return None
    yield


def publish_d1_remote(ctx: JobContext, input: dict) -> Generator[Any, Any, None]:
    subprocess.run(["rs", "deploy"], cwd=WEBSITE_DIRECTORY, check=True)
    return None
    yield


def publish_github(ctx: JobContext, input: dict) -> Generator[Any, Any, str | None]:
    """Push the manifest to GitHub through a throwaway clone."""
    with tempfile.TemporaryDirectory(prefix="mirror-github-") as scratch_dir:
        return publish_manifest(scratch_dir)
    yield


def build_website(ctx: JobContext, input: dict) -> Generator[Any, Any, None]:
    yield ctx.scope.build_source({})
    yield ctx.scope.publish_d1_remote({})
