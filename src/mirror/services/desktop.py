"""Open local directories in the desktop file manager."""

import subprocess


def open_directory(path: str) -> None:
    """Open a directory in Nautilus."""
    subprocess.Popen(["nautilus", path])
