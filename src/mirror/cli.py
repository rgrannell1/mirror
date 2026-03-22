
import logging
import multiprocessing

from mirror.workflows.enrich.enrich import EnrichData, EnrichPlace
from mirror.workflows.publish.publish import PublishArtifacts, PublishAtom, PublishEnv, PublishStats, PublishTriples
from mirror.workflows.scan.scan import GeonamesScan, MediaScan, ScanMedia, WikidataScan, ReadAlbums, ReadPhotos
from mirror.workflows.workflow import MirrorWorkflow

logging.basicConfig(level=logging.INFO, force=True)
logging.getLogger("PIL").setLevel(logging.WARNING)

from zahir import ConcurrencyLimit, LocalScope, LocalWorkflow, MemoryContext, SQLiteJobRegistry

from mirror.workflows.upload import (
    ComputeContrastingGrey,
    ComputeImageMosaic,
    UploadMissingPhotos,
    UploadMissingVideos,
    UploadMedia,
    UploadPhoto,
    UploadVideo,
    UploadVideoThumbnail,
)


def main():
    """Execute the upload media workflow"""

    if multiprocessing.get_start_method() != "fork":
        multiprocessing.set_start_method("fork", force=True)

    job_registry = SQLiteJobRegistry("mirror_jobs.db")
    context = MemoryContext(
        scope=LocalScope(
            dependencies=[ConcurrencyLimit],
            specs=[
                ComputeContrastingGrey,
                ComputeImageMosaic,
                UploadPhoto,
                UploadMissingPhotos,
                UploadVideo,
                UploadMissingVideos,
                UploadMedia,
                UploadVideoThumbnail,
                MirrorWorkflow,
                EnrichData,
                EnrichPlace,
                PublishArtifacts,
                PublishEnv,
                PublishAtom,
                PublishStats,
                PublishTriples,
                ScanMedia,
                MediaScan,
                GeonamesScan,
                WikidataScan,
                ReadAlbums,
                ReadPhotos
            ],
        ),
        job_registry=job_registry,
    )

    start = MirrorWorkflow({
        "upload_videos": False,
        "upload_images": True
    }, {})
    # Disable tracing (otel_output_dir=None) to avoid slow event-loop I/O; re-enable for debugging
    for event in LocalWorkflow(context, max_workers=15, otel_output_dir=None).run(start):
        print(event)


if __name__ == "__main__":
    main()
