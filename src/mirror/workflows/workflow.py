import os
from collections.abc import Generator
from typing import Any

from zahir import JobContext, check_file_dependency

from mirror.commons.config import OUTPUT_DIRECTORY
from mirror.workflows.scan.utils import DEFAULT_ALBUMS_MARKDOWN_PATH, DEFAULT_PHOTOS_MARKDOWN_PATH
from mirror.workflows.workflow_types import MirrorWorkflowInput


def upload_media_input(input: MirrorWorkflowInput) -> dict:
    """Forward the upload flags from the workflow input."""
    return {
        "force_recompute_grey": input.get("force_recompute_grey", False),
        "force_recompute_mosaic": input.get("force_recompute_mosaic", False),
        "force_upload_images": input.get("force_upload_images", False),
        "force_upload_videos": input.get("force_upload_videos", False),
        "force_roles": input.get("force_roles"),
        "upload_images": input.get("upload_images"),
        "upload_videos": input.get("upload_videos"),
    }


def run_scan(ctx: JobContext, paths: dict) -> Generator[Any, Any, bool]:
    """Run scan_media; report whether it succeeded."""
    try:
        yield ctx.scope.scan_media({
            "albums_markdown_path": paths["albums_markdown_path"],
            "photos_markdown_path": paths["photos_markdown_path"],
        })
    except Exception as err:  # noqa: BLE001
        print(f"WARNING: scan_media failed: {err}")
        return False

    return True


def publish_phase(
    ctx: JobContext, input: MirrorWorkflowInput, paths: dict
) -> Generator[Any, Any, str]:
    """Publish artifacts, rebuild the site, verify the outputs, and push to GitHub.

    Returns a one-line summary of what was published.
    """
    print("publishing artifacts")

    result = yield ctx.scope.publish_artifacts(paths)

    yield ctx.scope.build_source({})
    yield ctx.scope.run_integration_tests({})

    pid = result["publication_id"]
    tribbles_expanded_path = os.path.join(paths["output_dir"], f"tribbles-expanded.{pid}.txt")
    yield from check_file_dependency(tribbles_expanded_path)

    if input.get("publish_d1"):
        yield ctx.scope.publish_d1_remote({})

    summary = yield from push_manifest_phase(ctx)
    return summary


def push_manifest_phase(ctx: JobContext) -> Generator[Any, Any, str]:
    """Push the manifest to GitHub and describe the outcome."""
    message = yield ctx.scope.publish_github({})

    if message:
        return f"published to github: {message}"
    return "manifest matches github, nothing published"


def mirror_workflow(ctx: JobContext, input: MirrorWorkflowInput) -> Generator[Any, Any, str]:
    artifact_paths = {
        "output_dir": input.get("manifest_output_dir", OUTPUT_DIRECTORY),
        "albums_markdown_path": input.get("albums_markdown_path", DEFAULT_ALBUMS_MARKDOWN_PATH),
        "photos_markdown_path": input.get("photos_markdown_path", DEFAULT_PHOTOS_MARKDOWN_PATH),
    }

    scan_ok = yield from run_scan(ctx, artifact_paths)

    yield ctx.scope.upload_media(upload_media_input(input))

    if not scan_ok:
        # scan loads albums.md/photos.md into the DB via read_albums/read_photos. If it failed the
        # DB is stale, and write_metadata rewrites the whole markdown file from the DB — which would
        # silently overwrite the human-edited ratings. Bail out before any destructive write or
        # publish; resume the run once scan is fixed.
        print(
            "scan failed: skipping metadata rewrite and publish"
            " to avoid overwriting albums.md/photos.md from a stale database"
        )
        return "scan failed: nothing published"

    # Phase A (ungated): rewrite albums.md/photos.md so freshly-indexed photos become labellable.
    yield ctx.scope.write_metadata(artifact_paths)

    # Gate: block outward publication if the metadata is not publish-ready.
    yield ctx.scope.audit_media({})

    summary = yield from publish_phase(ctx, input, artifact_paths)
    return summary
