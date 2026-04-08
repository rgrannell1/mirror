"""TypedDict inputs for scan workflow jobs."""

from __future__ import annotations

from typing import TypedDict


class MediaScanInput(TypedDict, total=False):
    dpath: str


class MarkdownReadInput(TypedDict, total=False):
    markdown_path: str


class EmptyScanInput(TypedDict):
    """Steps that ignore input but accept `{}` from the runner."""

    pass
