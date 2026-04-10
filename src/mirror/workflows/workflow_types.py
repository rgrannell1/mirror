"""Types for the top-level `MirrorWorkflow`."""

from __future__ import annotations

from typing import TypedDict


class MirrorWorkflowInput(TypedDict, total=False):
    upload_images: bool
    upload_videos: bool
    force_recompute_grey: bool
    force_recompute_mosaic: bool
    force_upload_images: bool
    force_upload_videos: bool
    albums_markdown_path: str
    photos_markdown_path: str
    # Overrides config `OUTPUT_DIRECTORY` when set
    manifest_output_dir: str
