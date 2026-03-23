from zahir import Await, Context, spec

from mirror.commons.config import OUTPUT_DIRECTORY
from mirror.workflows.enrich.enrich import EnrichData
from mirror.workflows.publish.publish import PublishArtifacts
from mirror.workflows.scan.scan import ScanMedia
from mirror.workflows.scan.utils import DEFAULT_ALBUMS_MARKDOWN_PATH, DEFAULT_PHOTOS_MARKDOWN_PATH
from mirror.workflows.upload.upload import UploadMedia
from mirror.workflows.workflow_types import MirrorWorkflowInput


@spec()
def MirrorWorkflow(
    context: Context,
    input: MirrorWorkflowInput,
    dependencies: dict,
):
    albums_markdown_path = input.get("albums_markdown_path", DEFAULT_ALBUMS_MARKDOWN_PATH)
    photos_markdown_path = input.get("photos_markdown_path", DEFAULT_PHOTOS_MARKDOWN_PATH)
    manifest_output_dir = input.get("manifest_output_dir", OUTPUT_DIRECTORY)

    yield EnrichData({}, {})

    yield Await(
        ScanMedia(
            {
                "albums_markdown_path": albums_markdown_path,
                "photos_markdown_path": photos_markdown_path,
            },
            {},
        )
    )

    yield Await(
        UploadMedia(
            {
                "force_recompute_grey": False,
                "force_recompute_mosaic": False,
                "force_upload_images": False,
                "force_upload_videos": False,
                "upload_images": input.get("upload_images"),
                "upload_videos": input.get("upload_videos"),
            },
            {},
        )
    )

    yield Await(
        PublishArtifacts(
            {
                "output_dir": manifest_output_dir,
                "albums_markdown_path": albums_markdown_path,
                "photos_markdown_path": photos_markdown_path,
            },
            {},
        )
    )
