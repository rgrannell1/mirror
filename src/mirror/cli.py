import argparse
import logging
import multiprocessing

from zahir import evaluate, with_progress, make_telemetry

from mirror.workflows.scan.scan import (
    geonames_scan,
    media_scan,
    read_albums,
    read_photos,
    read_videos,
    scan_media,
    wikidata_scan,
)
from mirror.workflows.upload.upload import (
    compute_contrasting_grey,
    compute_image_mosaic,
    upload_media,
    upload_missing_photos,
    upload_missing_videos,
    upload_photo,
    upload_video,
    upload_video_thumbnail,
)
from mirror.workflows.publish.publish import (
    publish_artifacts,
    publish_atom,
    publish_d1,
    publish_env,
    publish_stats,
    publish_triples,
    update_albums_markdown,
    update_photos_markdown,
    update_videos_markdown,
)
from mirror.workflows.website.website import build_source, publish_d1_remote
from mirror.workflows.workflow import mirror_workflow

logging.basicConfig(level=logging.INFO, force=True)
logging.getLogger("PIL").setLevel(logging.WARNING)

SCOPE = {
    "mirror_workflow": mirror_workflow,
    "scan_media": scan_media,
    "media_scan": media_scan,
    "geonames_scan": geonames_scan,
    "wikidata_scan": wikidata_scan,
    "read_albums": read_albums,
    "read_photos": read_photos,
    "read_videos": read_videos,
    "compute_contrasting_grey": compute_contrasting_grey,
    "compute_image_mosaic": compute_image_mosaic,
    "upload_photo": upload_photo,
    "upload_missing_photos": upload_missing_photos,
    "upload_video_thumbnail": upload_video_thumbnail,
    "upload_video": upload_video,
    "upload_missing_videos": upload_missing_videos,
    "upload_media": upload_media,
    "publish_env": publish_env,
    "publish_atom": publish_atom,
    "publish_stats": publish_stats,
    "publish_triples": publish_triples,
    "publish_d1": publish_d1,
    "update_albums_markdown": update_albums_markdown,
    "update_photos_markdown": update_photos_markdown,
    "update_videos_markdown": update_videos_markdown,
    "publish_artifacts": publish_artifacts,
    "build_source": build_source,
    "publish_d1_remote": publish_d1_remote,
}


def main():
    """Execute the mirror media pipeline"""

    parser = argparse.ArgumentParser(description="Mirror media pipeline")
    parser.add_argument("--no-upload-images", dest="upload_images", action="store_false", default=True)
    parser.add_argument("--no-upload-videos", dest="upload_videos", action="store_false", default=True)
    parser.add_argument("--force-recompute-grey", dest="force_recompute_grey", action="store_true", default=False)
    parser.add_argument("--force-recompute-mosaic", dest="force_recompute_mosaic", action="store_true", default=False)
    parser.add_argument("--force-upload-images", dest="force_upload_images", action="store_true", default=False)
    parser.add_argument("--force-upload-videos", dest="force_upload_videos", action="store_true", default=False)
    parser.add_argument("--force-roles", dest="force_roles", nargs="+", default=None, metavar="ROLE")
    parser.add_argument("--publish-d1", dest="publish_d1", action="store_true", default=False)
    args = parser.parse_args()

    if multiprocessing.get_start_method() != "fork":
        multiprocessing.set_start_method("fork", force=True)

    workflow_input = {
        "upload_images": args.upload_images,
        "upload_videos": args.upload_videos,
        "force_recompute_grey": args.force_recompute_grey,
        "force_recompute_mosaic": args.force_recompute_mosaic,
        "force_upload_images": args.force_upload_images,
        "force_upload_videos": args.force_upload_videos,
        "force_roles": args.force_roles,
        "publish_d1": args.publish_d1,
    }

    for _ in with_progress(
        evaluate("mirror_workflow", (workflow_input,), scope=SCOPE, n_workers=15, handler_wrappers=[make_telemetry()])
    ):
        pass
