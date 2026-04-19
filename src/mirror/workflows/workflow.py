from collections.abc import Generator
from typing import Any

from zahir.core.evaluate import JobContext

from mirror.commons.config import OUTPUT_DIRECTORY
from mirror.workflows.scan.utils import DEFAULT_ALBUMS_MARKDOWN_PATH, DEFAULT_PHOTOS_MARKDOWN_PATH
from mirror.workflows.workflow_types import MirrorWorkflowInput


def mirror_workflow(ctx: JobContext, input: MirrorWorkflowInput) -> Generator[Any, Any, None]:
    albums_markdown_path = input.get("albums_markdown_path", DEFAULT_ALBUMS_MARKDOWN_PATH)
    photos_markdown_path = input.get("photos_markdown_path", DEFAULT_PHOTOS_MARKDOWN_PATH)
    manifest_output_dir = input.get("manifest_output_dir", OUTPUT_DIRECTORY)

    try:
        yield ctx.scope.scan_media({
            "albums_markdown_path": albums_markdown_path,
            "photos_markdown_path": photos_markdown_path,
        })
    except Exception as err:
        print(f"WARNING: scan_media failed, continuing to publish: {err}")

    print("uploading media")

    yield ctx.scope.upload_media({
        "force_recompute_grey": input.get("force_recompute_grey", False),
        "force_recompute_mosaic": input.get("force_recompute_mosaic", False),
        "force_upload_images": input.get("force_upload_images", False),
        "force_upload_videos": input.get("force_upload_videos", False),
        "force_roles": input.get("force_roles"),
        "upload_images": input.get("upload_images"),
        "upload_videos": input.get("upload_videos"),
    })

    print("publishing artifacts")

    yield ctx.scope.publish_artifacts({
        "output_dir": manifest_output_dir,
        "albums_markdown_path": albums_markdown_path,
        "photos_markdown_path": photos_markdown_path,
    })

    if input.get("publish_d1"):
        yield ctx.scope.build_website({})
