import os
from collections.abc import Generator
from typing import Any

from zahir import JobContext, check_file_dependency

from mirror.commons.config import OUTPUT_DIRECTORY
from mirror.workflows.scan.utils import DEFAULT_ALBUMS_MARKDOWN_PATH, DEFAULT_PHOTOS_MARKDOWN_PATH
from mirror.workflows.workflow_types import MirrorWorkflowInput


def mirror_workflow(ctx: JobContext, input: MirrorWorkflowInput) -> Generator[Any, Any, None]:
    albums_markdown_path = input.get("albums_markdown_path", DEFAULT_ALBUMS_MARKDOWN_PATH)
    photos_markdown_path = input.get("photos_markdown_path", DEFAULT_PHOTOS_MARKDOWN_PATH)
    manifest_output_dir = input.get("manifest_output_dir", OUTPUT_DIRECTORY)

    scan_ok = True
    try:
        yield ctx.scope.scan_media({
            "albums_markdown_path": albums_markdown_path,
            "photos_markdown_path": photos_markdown_path,
        })
    except Exception as err:  # noqa: BLE001
        scan_ok = False
        print(f"WARNING: scan_media failed: {err}")

    yield ctx.scope.upload_media({
        "force_recompute_grey": input.get("force_recompute_grey", False),
        "force_recompute_mosaic": input.get("force_recompute_mosaic", False),
        "force_upload_images": input.get("force_upload_images", False),
        "force_upload_videos": input.get("force_upload_videos", False),
        "force_roles": input.get("force_roles"),
        "upload_images": input.get("upload_images"),
        "upload_videos": input.get("upload_videos"),
    })

    if not scan_ok:
        # scan loads albums.md/photos.md into the DB via read_albums/read_photos. If it failed the
        # DB is stale, and write_metadata rewrites the whole markdown file from the DB — which would
        # silently overwrite the human-edited ratings. Bail out before any destructive write or
        # publish; resume the run once scan is fixed.
        print("scan failed: skipping metadata rewrite and publish to avoid overwriting albums.md/photos.md from a stale database")
        return

    # Phase A (ungated): rewrite albums.md/photos.md so freshly-indexed photos become labellable.
    yield ctx.scope.write_metadata({
        "output_dir": manifest_output_dir,
        "albums_markdown_path": albums_markdown_path,
        "photos_markdown_path": photos_markdown_path,
    })

    # Gate: block outward publication if the metadata is not publish-ready.
    yield ctx.scope.audit_media({})

    print("publishing artifacts")

    result = yield ctx.scope.publish_artifacts({
        "output_dir": manifest_output_dir,
        "albums_markdown_path": albums_markdown_path,
        "photos_markdown_path": photos_markdown_path,
    })

    yield ctx.scope.build_source({})
    yield ctx.scope.run_integration_tests({})

    pid = result["publication_id"]
    tribbles_expanded_path = os.path.join(manifest_output_dir, f"tribbles-expanded.{pid}.txt")
    yield from check_file_dependency(tribbles_expanded_path)

    if input.get("publish_d1"):
        yield ctx.scope.publish_d1_remote({})
