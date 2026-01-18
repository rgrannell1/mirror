from __future__ import annotations

from typing import TypedDict


from zahir import (
    ConcurrencyLimit,
    ResourceLimit,
    DependencyGroup,
    LocalScope,
    SQLiteJobRegistry,
    MemoryContext,
    LocalWorkflow,
)
from typing import Generator, Iterator, TypedDict

from mirror.cdn import CDN
from mirror.config import DATABASE_PATH
from mirror.constants import FULL_SIZED_VIDEO_ROLE, IMAGE_ENCODINGS, VIDEO_ENCODINGS
from mirror.database import SqliteDatabase
from mirror.encoder import PhotoEncoder, VideoEncoder

from zahir import (
    JobInstance,
    JobOutputEvent,
    spec,
    Await,
    Context,
    WorkflowOutputEvent,
)


class PhotoJobInput(TypedDict):
    fpath: str


class UploadOpts(TypedDict):
    force_recompute_grey: bool
    force_recompute_mosaic: bool
    force_upload_images: bool
    force_upload_videos: bool


def list_photos_without_mosaic(db: SqliteDatabase, force_recompute: bool = False) -> Generator[str]:
    photos = db.photos_table()
    encoded_photos_table = db.encoded_photos_table()

    for fpath in photos.list():
        encodings = list(encoded_photos_table.list_for_file(fpath))
        published_roles = {enc.role for enc in encodings}

        if "thumbnail_mosaic" not in published_roles or force_recompute:
            yield fpath


def list_photos_without_contrasting_grey(db: SqliteDatabase, force_recompute: bool = False) -> Iterator[str]:
    photos = db.photos_table()
    icons = db.photo_icon_table()

    for fpath in photos.list():
        if not icons.get_by_fpath(fpath) or force_recompute:
            yield fpath


def list_photos_without_upload(db: SqliteDatabase, force_upload: bool = False) -> Iterator[str]:
    photos = db.photos_table()
    encoded_photos_table = db.encoded_photos_table()

    for fpath in photos.list():
        encodings = list(encoded_photos_table.list_for_file(fpath))
        published_roles = {enc.role for enc in encodings}

        needs_upload = False
        for role, params in IMAGE_ENCODINGS.items():
            if role in published_roles:
                continue

            # only generate social-cards for album covers, for the moment
            if "+cover" not in fpath and role == "social_card":
                continue

            needs_upload = True

        if needs_upload:
            yield fpath


def list_videos_without_upload(db: SqliteDatabase, force_upload: bool = False) -> Iterator[str]:
    videos = db.videos_table().list()
    encoded_videos_table = db.encoded_videos_table()

    for fpath in videos:
        encodings = list(encoded_videos_table.list_for_file(fpath))
        published_roles = {enc.role for enc in encodings}
        needs_upload = False

        for role, params in VIDEO_ENCODINGS:
            if role in published_roles:
                continue

            needs_upload = True

        if needs_upload:
            yield fpath


def is_silent(fpath: str) -> bool:
    """is a video silent?"""
    return "+silent" not in fpath


def publish_video_encoding(cdn, db, fpath, role, params):
    width, height, bitrate = params["width"], params["height"], params["bitrate"]
    uploaded_video_name = CDN.video_name(fpath, bitrate, width, height, "webm")

    encoded_path = VideoEncoder.encode(
        fpath=fpath,
        upload_file_name=uploaded_video_name,
        video_bitrate=bitrate,
        width=width,
        height=height,
        share_audio=is_silent(fpath),
    )

    if not encoded_path:
        raise Exception("Failed to encode video")

    uploaded_video_url = cdn.upload_file_public(name=uploaded_video_name, encoded_path=encoded_path)
    print(f"published {fpath} as {uploaded_video_url}")

    db.encoded_videos_table().add(fpath, uploaded_video_url, role, "webm")

    return encoded_path


def publish_video_thumbnail(cdn, db, fpath, encoded_path):
    THUMBNAIL_FORMAT = "webp"
    THUMBNAIL_ROLE = "video_thumbnail_webp"
    encoded_thumbnail = VideoEncoder.encode_thumbnail(
        encoded_path, {"format": THUMBNAIL_FORMAT, "quality": 85, "method": 6}
    )

    thumbnail_url = cdn.upload_photo(encoded_data=encoded_thumbnail, role=THUMBNAIL_ROLE, format=THUMBNAIL_FORMAT)
    db.encoded_photos_table().add(fpath=fpath, url=thumbnail_url, role=THUMBNAIL_ROLE, format=THUMBNAIL_FORMAT)


@spec()
def ComputeContrastingGrey(
    spec_args,
    context: Context,
    input: PhotoJobInput,
    dependencies={},
) -> Generator[None]:
    fpath = input["fpath"]

    db = SqliteDatabase(DATABASE_PATH)
    icons = db.photo_icon_table()

    grey_value = PhotoEncoder.compute_contrasting_grey(fpath)
    icons.add(fpath, grey_value)

    yield


@spec()
def ComputeMosaic(
    spec_args,
    context: Context,
    input: PhotoJobInput,
    dependencies: DependencyGroup,
) -> Generator[None]:
    fpath = input["fpath"]

    db = SqliteDatabase(DATABASE_PATH)
    encoded_photos_table = db.encoded_photos_table()

    v2 = PhotoEncoder.encode_image_colours(fpath)
    v2_content = "".join(v2)

    encoded_photos_table.add(fpath, v2_content, "thumbnail_mosaic", "custom")

    yield


@spec()
def UploadPhoto(
    spec_args,
    context: Context,
    input: dict,
    dependencies={},
) -> Generator[JobOutputEvent]:
    fpath = input["fpath"]
    role = input["role"]
    params = input["params"]

    cdn_limit = dependencies.get("cdn_limit")

    cdn = CDN()
    db = SqliteDatabase(DATABASE_PATH)

    with cdn_limit:
        uploaded_url = cdn.upload_photo(
            encoded_data=PhotoEncoder.encode(fpath, role, params),
            role=role,
            format=params["format"],  # type: ignore
        )
        encoded_photos_table = db.encoded_photos_table()
        encoded_photos_table.add(fpath, uploaded_url, role, params["format"])

    yield JobOutputEvent({"fpath": fpath, "role": role, "url": uploaded_url})


@spec()
def FindMissingPhotos(
    spec_args,
    context: Context,
    input: PhotoJobInput,
    dependencies={},
) -> Generator[JobInstance]:
    fpath = input["fpath"]

    db = SqliteDatabase(DATABASE_PATH)
    encoded_photos_table = db.encoded_photos_table()

    encodings = list(encoded_photos_table.list_for_file(fpath))
    published_roles = {enc.role for enc in encodings}

    # Use a fixed semaphore_id so all photo uploads share the same limit
    cdn_limit = ConcurrencyLimit(2, 1, context, semaphore_id="global_photo_cdn_limit")

    for role, params in IMAGE_ENCODINGS.items():
        if role in published_roles:
            continue

        # only generate social-cards for album covers, for the moment
        if "+cover" not in fpath and role == "social_card":
            continue

        yield UploadPhoto({"fpath": fpath, "role": role, "params": params}, {"cdn_limit": cdn_limit})


@spec()
def UploadVideoThumbnail(
    spec_args,
    context: Context,
    input: dict,
    dependencies={},
) -> Generator[JobOutputEvent]:
    fpath = input["fpath"]
    encoded_path = input["encoded_path"]

    cdn = CDN()
    db = SqliteDatabase(DATABASE_PATH)

    publish_video_thumbnail(cdn, db, fpath, encoded_path)

    yield JobOutputEvent({"fpath": fpath})


@spec()
def UploadVideo(
    spec_args,
    context: Context,
    input: dict,
    dependencies={},
) -> Generator[JobOutputEvent | JobInstance]:
    fpath = input["fpath"]
    role = input["role"]
    params = input["params"]

    cdn_limit = dependencies.get("cdn_limit")

    cdn = CDN()
    db = SqliteDatabase(DATABASE_PATH)

    with cdn_limit:
        encoded_path = publish_video_encoding(cdn, db, fpath, role, params)

        if role == FULL_SIZED_VIDEO_ROLE:
            yield UploadVideoThumbnail({"fpath": fpath, "encoded_path": encoded_path})

    yield JobOutputEvent({"fpath": fpath, "role": role})


@spec()
def FindMissingVideos(
    spec_args,
    context: Context,
    input: PhotoJobInput,
    dependencies={},
) -> Generator[JobInstance]:
    fpath = input["fpath"]

    db = SqliteDatabase(DATABASE_PATH)
    encoded_videos_table = db.encoded_videos_table()

    encodings = list(encoded_videos_table.list_for_file(fpath))
    published_roles = {enc.role for enc in encodings}

    cdn_limit = ConcurrencyLimit(1, 1, context, semaphore_id="global_video_cdn_limit")
    oom_limit = ResourceLimit(resource="memory", max_percent=55)

    for role, params in VIDEO_ENCODINGS:
        if role in published_roles:
            continue

        yield UploadVideo(
            {"fpath": fpath, "role": role, "params": params}, {"cdn_limit": cdn_limit, "oom_limit": oom_limit}
        )


@spec()
def UploadMedia(
    spec_args,
    context: Context,
    input: UploadOpts,
    dependencies={},
) -> Generator[Await | WorkflowOutputEvent]:
    db = SqliteDatabase(DATABASE_PATH)

    force_recompute_grey = input.get("force_recompute_grey", False)
    force_recompute_mosaic = input.get("force_recompute_mosaic", False)
    force_upload_images = input.get("force_upload_images", False)
    force_upload_videos = input.get("force_upload_videos", False)

    for fpath in list_photos_without_contrasting_grey(db, force_recompute_grey):
        yield ComputeContrastingGrey({"fpath": fpath})

    for fpath in list_photos_without_mosaic(db, force_recompute_mosaic):
        yield ComputeMosaic({"fpath": fpath})

    for fpath in list_photos_without_upload(db, force_upload_images):
        yield FindMissingPhotos({"fpath": fpath})

    for fpath in list_videos_without_upload(db, force_upload_videos):
        yield FindMissingVideos({"fpath": fpath})


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


import logging

logging.basicConfig(level=logging.INFO, force=True)
logging.getLogger("PIL").setLevel(logging.WARNING)


if __name__ == "__main__":
    main()
