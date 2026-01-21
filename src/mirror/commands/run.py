
import logging

logging.basicConfig(level=logging.INFO, force=True)
logging.getLogger("PIL").setLevel(logging.WARNING)

from zahir import ConcurrencyLimit, LocalScope, LocalWorkflow, MemoryContext, SQLiteJobRegistry

from mirror.commands.upload import ComputeContrastingGrey, ComputeMosaic, FindMissingPhotos, FindMissingVideos, UploadMedia, UploadPhoto, UploadVideo, UploadVideoThumbnail

def main():
    """Execute the upload media workflow"""
    import multiprocessing

    if multiprocessing.get_start_method() != "fork":
        multiprocessing.set_start_method("fork", force=True)

    job_registry = SQLiteJobRegistry("mirror_jobs.db")
    context = MemoryContext(
        scope=LocalScope(
            dependencies=[ConcurrencyLimit],
            specs=[
                ComputeContrastingGrey,
                ComputeMosaic,
                UploadPhoto,
                FindMissingPhotos,
                UploadVideo,
                FindMissingVideos,
                UploadMedia,
                UploadVideoThumbnail
            ],
        ),
        job_registry=job_registry,
    )

    start = UploadMedia(
        {
            "force_recompute_grey": False,
            "force_recompute_mosaic": False,
            "force_upload_images": False,
            "force_upload_videos": False,
        }
    )

    for event in LocalWorkflow(context, max_workers=15).run(start):
        print(event)


if __name__ == "__main__":
    main()
