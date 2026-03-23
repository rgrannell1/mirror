"""Typed inputs for the publish workflow."""

from __future__ import annotations

from typing import NotRequired, Required, TypedDict


class PublishArtifactsInput(TypedDict, total=False):
    """Arguments for `PublishArtifacts` (markdown paths default inside the job if omitted)."""

    output_dir: Required[str]
    albums_markdown_path: NotRequired[str]
    photos_markdown_path: NotRequired[str]


class PublishArtifactBundleInput(TypedDict):
    """Shared input passed to each parallel publish step after `publication_id` is allocated."""

    output_dir: str
    publication_id: str
    albums_markdown_path: str
    photos_markdown_path: str
