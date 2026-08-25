"""Website build workflow: build source and publish D1 database remotely."""

from __future__ import annotations

from collections.abc import Generator
from typing import Any

from zahir import JobContext

from mirror.services.github import publish_manifest
from mirror.services.website import run_website_step


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
