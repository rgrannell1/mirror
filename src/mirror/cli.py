
import argparse
import logging
import multiprocessing
from pathlib import Path

from mirror.workflows.workflow import MirrorWorkflow

logging.basicConfig(level=logging.INFO, force=True)
logging.getLogger("PIL").setLevel(logging.WARNING)

from zahir import LocalScope, LocalWorkflow, MemoryContext, SQLiteJobRegistry


def main():
    """Execute the upload media workflow"""

    parser = argparse.ArgumentParser(description="Mirror media pipeline")
    parser.add_argument("--no-upload-images", dest="upload_images", action="store_false", default=True)
    parser.add_argument("--no-upload-videos", dest="upload_videos", action="store_false", default=True)
    parser.add_argument("--force-recompute-grey", dest="force_recompute_grey", action="store_true", default=False)
    parser.add_argument("--force-recompute-mosaic", dest="force_recompute_mosaic", action="store_true", default=False)
    parser.add_argument("--force-upload-images", dest="force_upload_images", action="store_true", default=False)
    parser.add_argument("--force-upload-videos", dest="force_upload_videos", action="store_true", default=False)
    parser.add_argument("--publish-d1", dest="publish_d1", action="store_true", default=False)
    args = parser.parse_args()

    if multiprocessing.get_start_method() != "fork":
        multiprocessing.set_start_method("fork", force=True)

    job_registry = SQLiteJobRegistry("mirror_jobs.db")
    context = MemoryContext(
        scope=LocalScope().scan(Path(__file__).parent),
        job_registry=job_registry,
    )

    start = MirrorWorkflow({
        "upload_images": args.upload_images,
        "upload_videos": args.upload_videos,
        "force_recompute_grey": args.force_recompute_grey,
        "force_recompute_mosaic": args.force_recompute_mosaic,
        "force_upload_images": args.force_upload_images,
        "force_upload_videos": args.force_upload_videos,
        "publish_d1": args.publish_d1,
    }, {})
    for event in LocalWorkflow(context, max_workers=15).run(start):
        print(event)


if __name__ == "__main__":
    main()
