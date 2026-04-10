"""Website build workflow: build source and publish D1 database remotely."""

from __future__ import annotations

import subprocess
from typing import Generator

from zahir import Await, Context, spec

from mirror.commons.config import WEBSITE_DIRECTORY


@spec()
def BuildSource(
    context: Context,
    input: dict,
    dependencies: dict,
) -> Generator:
    subprocess.run(["rs", "dev", "--build-only"], cwd=WEBSITE_DIRECTORY, check=True, stderr=None)
    yield


@spec()
def PublishD1Remote(
    context: Context,
    input: dict,
    dependencies: dict,
) -> Generator:
    subprocess.run(["rs", "deploy"], cwd=WEBSITE_DIRECTORY, check=True)
    yield


@spec()
def BuildWebsite(
    context: Context,
    input: dict,
    dependencies: dict,
) -> Generator[Await]:
    yield Await(
        [
            BuildSource(),
            PublishD1Remote(),
        ]
    )
