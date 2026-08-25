"""Start and inspect the Badger media clustering process."""

import subprocess
from pathlib import Path

from mirror.commons.config import BADGER_PATH


def start_badger(destination: str) -> subprocess.Popen[str]:
    """Start Badger with JSON progress output."""
    source_glob = str(Path(destination) / "*")
    return subprocess.Popen(
        [
            BADGER_PATH,
            "cluster",
            "--from",
            source_glob,
            "--to",
            destination,
            "--yes",
            "--json-progress",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def check_badger_exit(process: subprocess.Popen[str]) -> None:
    """Raise when Badger exits unsuccessfully."""
    if process.returncode == 0:
        return
    stderr_output = process.stderr.read() if process.stderr else ""
    raise RuntimeError(f"badger exited {process.returncode}: {stderr_output.strip()}")
