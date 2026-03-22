from zahir import Await, spec

from mirror.workflows.enrich.enrich import EnrichData
from mirror.workflows.publish.publish import PublishArtifacts
from mirror.workflows.scan.scan import ScanMedia
from mirror.workflows.upload.upload import UploadMedia


@spec()
def MirrorWorkflow(context, input, dependencies):
    yield EnrichData({}, {})

    yield Await(
        ScanMedia(
            {
                "albums_markdown_path": input.get("albums_markdown_path", "albums.md"),
                "photos_markdown_path": input.get("photos_markdown_path", "photos.md"),
            }
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
            }
        )
    )

    yield Await(PublishArtifacts({"output_dir": "/home/rg/Code/websites/photos.rgrannell.xyz/manifest"}))
