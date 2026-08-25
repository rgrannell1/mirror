"""Run build and deployment commands for the photo website."""

import subprocess

from mirror.commons.config import WEBSITE_DIRECTORY
from mirror.commons.constants import BUILD_OUTPUT_TAIL_LINES
from mirror.commons.exceptions import WebsiteBuildError


def run_website_step(command: list[str]) -> None:
    """Run a website command and raise with the output tail on failure."""
    result = subprocess.run(command, cwd=WEBSITE_DIRECTORY, capture_output=True, text=True)
    if result.returncode == 0:
        return

    lines = (result.stdout + result.stderr).splitlines()
    tail = "\n".join(lines[-BUILD_OUTPUT_TAIL_LINES:])
    raise WebsiteBuildError(f"`{' '.join(command)}` exited {result.returncode}:\n{tail}")
