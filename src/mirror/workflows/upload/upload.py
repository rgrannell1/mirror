from __future__ import annotations


from zahir import ConcurrencyLimit, ResourceLimit, DependencyGroup, SqliteDependency
from typing import Generator

from mirror.services.cdn import CDN
from mirror.workflows.upload.utils import (
    PhotoJobInput,
    UploadOpts,
    list_photos_without_contrasting_grey,
    list_photos_without_mosaic,
    list_photos_without_upload,
    list_videos_without_upload,
    publish_video_encoding,
    publish_video_thumbnail,
)
from mirror.commons.config import DATABASE_PATH
from mirror.commons.constants import FULL_SIZED_VIDEO_ROLE, IMAGE_ENCODINGS, VIDEO_ENCODINGS
from mirror.services.database import SqliteDatabase
from mirror.services.encoder import PhotoEncoder

from zahir import (
    JobInstance,
    JobOutputEvent,
    spec,
    Await,
    Context,
    WorkflowOutputEvent,
)


@spec()
def ComputeContrastingGrey(
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
def ComputeImageMosaic(
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
    context: Context,
    input: dict,
    dependencies={},
) -> Generator[SqliteDependency | JobOutputEvent | Await]:
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

    # Check it actually uploaded; throw if not
    yield Await(
        SqliteDependency(
            DATABASE_PATH,
            """
    select case when exists(select 1 from encoded_photos where fpath = ? and role = ? and url = ?) then 'satisfied' else 'impossible' end as status
    """,
            (fpath, role, uploaded_url),
        )
    )

    yield JobOutputEvent({"fpath": fpath, "role": role, "url": uploaded_url})


@spec()
def UploadMissingPhotos(
    context: Context,
    input: PhotoJobInput,
    dependencies={},
) -> Generator[JobInstance]:
    fpath = input["fpath"]
    force = input.get("force", False)

    db = SqliteDatabase(DATABASE_PATH)
    encoded_photos_table = db.encoded_photos_table()

    encodings = list(encoded_photos_table.list_for_file(fpath))
    published_roles = {enc.role for enc in encodings if enc.url and enc.url.strip()}

    # Use a fixed semaphore_id so all photo uploads share the same limit
    cdn_limit = ConcurrencyLimit(2, 1, context, semaphore_id="global_photo_cdn_limit")

    for role, params in IMAGE_ENCODINGS.items():
        if role in published_roles:
            continue

        # only generate social-cards for album covers, for the moment
        if "+cover" not in fpath and role == "social_card":
            continue

        yield UploadPhoto({"fpath": fpath, "role": role, "params": params}, {"cdn_limit": cdn_limit}, once=not force)


@spec()
def UploadVideoThumbnail(
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
    context: Context,
    input: dict,
    dependencies={},
) -> Generator[Await | JobOutputEvent | JobInstance]:
    fpath = input["fpath"]
    role = input["role"]
    params = input["params"]

    cdn_limit = dependencies.get("cdn_limit")

    cdn = CDN()
    db = SqliteDatabase(DATABASE_PATH)

    with cdn_limit:
        encoded_path = publish_video_encoding(cdn, db, fpath, role, params)
        yield Await(
            SqliteDependency(
                DATABASE_PATH,
                """
        select case when exists(select 1 from encoded_videos where fpath = ? and role = ? and url is not null and url != '') then 'satisfied' else 'impossible' end as status
        """,
                (fpath, role),
            )
        )

        # Only generate a thumbnail when we actually produced an encoded file
        if role == FULL_SIZED_VIDEO_ROLE and encoded_path:
            yield UploadVideoThumbnail({"fpath": fpath, "encoded_path": encoded_path})

    yield JobOutputEvent({"fpath": fpath, "role": role})


@spec()
def UploadMissingVideos(
    context: Context,
    input: PhotoJobInput,
    dependencies={},
) -> Generator[JobInstance | Await]:
    fpath = input["fpath"]
    force = input.get("force", False)

    db = SqliteDatabase(DATABASE_PATH)
    encoded_videos_table = db.encoded_videos_table()

    encodings = list(encoded_videos_table.list_for_file(fpath))
    published_roles = {enc.role for enc in encodings}

    cdn_limit = ConcurrencyLimit(1, 1, context, semaphore_id="global_video_cdn_limit")
    oom_limit = ResourceLimit(resource="memory", max_percent=65)

    for role, params in VIDEO_ENCODINGS:
        if role in published_roles:
            continue

        yield UploadVideo(
            {"fpath": fpath, "role": role, "params": params},
            {"cdn_limit": cdn_limit, "oom_limit": oom_limit},
            once=not force,
        )

    yield Await(
        SqliteDependency(
            DATABASE_PATH,
            """
    select case when (
        select count(distinct role) from encoded_videos
        where fpath = ?
        and role in ('video_libx264_unscaled', 'video_libx264_1080p', 'video_libx264_720p', 'video_libx264_480p')
        and url is not null
        and url != ''
    ) = 4 then 'satisfied' else 'unsatisfied' end as status
    """,
            (fpath,),
        )
    )


@spec()
def UploadMedia(
    context: Context,
    input: UploadOpts,
    dependencies={},
) -> Generator[Await | WorkflowOutputEvent]:
    db = SqliteDatabase(DATABASE_PATH)

    force_recompute_grey = input.get("force_recompute_grey", False)
    force_recompute_mosaic = input.get("force_recompute_mosaic", False)
    force_upload_images = input.get("force_upload_images", False)
    force_upload_videos = input.get("force_upload_videos", False)
    upload_images = input.get("upload_images")
    upload_videos = input.get("upload_videos")

    for fpath in list_photos_without_contrasting_grey(db, force_recompute_grey):
        yield ComputeContrastingGrey({"fpath": fpath, "force": force_recompute_grey}, {})

    for fpath in list_photos_without_mosaic(db, force_recompute_mosaic):
        yield ComputeImageMosaic({"fpath": fpath, "force": force_recompute_mosaic}, {})

    if upload_images:
        for fpath in list_photos_without_upload(db, force_upload_images):
            yield UploadMissingPhotos({"fpath": fpath, "force": force_upload_images}, {})

    if upload_videos:
        for fpath in list_videos_without_upload(db, force_upload_videos):
            yield UploadMissingVideos({"fpath": fpath, "force": force_upload_videos}, {})
