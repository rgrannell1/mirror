from __future__ import annotations

from typing import TypedDict


from zahir import (
    ConcurrencyLimit,
    DependencyGroup,
    LocalScope,
    SQLiteJobRegistry,
    MemoryContext,
    LocalWorkflow,
)
from typing import Generator, Iterator, TypedDict

from mirror.cdn import CDN
from mirror.config import DATABASE_PATH
from mirror.constants import IMAGE_ENCODINGS
from mirror.database import SqliteDatabase
from mirror.encoder import PhotoEncoder

from zahir import (
    Job,
    JobOutputEvent,
    job,
    Await,
    Context,
    WorkflowOutputEvent,
)


import logging

logging.basicConfig(level=logging.INFO, force=True)
logging.getLogger("PIL").setLevel(logging.WARNING)


class PhotoJobInput(TypedDict):
    fpath: str


class UploadOpts(TypedDict):
    force_recompute_grey: bool
    force_recompute_mosaic: bool
    force_upload_images: bool


def list_photos_without_mosaic(db: SqliteDatabase, force_recompute: bool = False) -> Iterator[str]:
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


@job()
def ComputeContrastingGrey(
    context: Context,
    input: PhotoJobInput,
    dependencies={},
) -> Iterator[None]:
    fpath = input["fpath"]

    db = SqliteDatabase(DATABASE_PATH)
    icons = db.photo_icon_table()

    grey_value = PhotoEncoder.compute_contrasting_grey(fpath)
    icons.add(fpath, grey_value)

    return iter(())


@job()
def ComputeMosaic(
    context: Context,
    input: PhotoJobInput,
    dependencies: DependencyGroup,
) -> Iterator[None]:
    fpath = input["fpath"]

    db = SqliteDatabase(DATABASE_PATH)
    encoded_photos_table = db.encoded_photos_table()

    v2 = PhotoEncoder.encode_image_colours(fpath)
    v2_content = "".join(v2)

    encoded_photos_table.add(fpath, v2_content, "thumbnail_mosaic", "custom")

    return iter(())


@job()
def UploadPhoto(
    context: Context,
    input: dict,
    dependencies={},
) -> Iterator:
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


@job()
def FindMissingPhotos(
    context: Context,
    input: PhotoJobInput,
    dependencies={},
) -> Iterator[Job]:
    fpath = input["fpath"]

    db = SqliteDatabase(DATABASE_PATH)
    encoded_photos_table = db.encoded_photos_table()

    encodings = list(encoded_photos_table.list_for_file(fpath))
    published_roles = {enc.role for enc in encodings}

    for role, params in IMAGE_ENCODINGS.items():
        if role in published_roles:
            continue

        # only generate social-cards for album covers, for the moment
        if "+cover" not in fpath and role == "social_card":
            continue

        cdn_limit = ConcurrencyLimit(2, 1)

        yield UploadPhoto({"fpath": fpath, "role": role, "params": params}, {"cdn_limit": cdn_limit})


@job()
def UploadMedia(
    context: Context,
    input: UploadOpts,
    dependencies={},
) -> Generator[Await | WorkflowOutputEvent]:
    db = SqliteDatabase(DATABASE_PATH)

    force_recompute_grey = input.get("force_recompute_grey", False)
    force_recompute_mosaic = input.get("force_recompute_mosaic", False)
    force_upload_images = input.get("force_upload_images", False)

    jobs: list[Job] = []

    for fpath in list_photos_without_contrasting_grey(db, force_recompute_grey):
        jobs.append(ComputeContrastingGrey({"fpath": fpath}))

    for fpath in list_photos_without_mosaic(db, force_recompute_mosaic):
        jobs.append(ComputeMosaic({"fpath": fpath}))

    for fpath in list_photos_without_upload(db, force_upload_images):
        jobs.append(FindMissingPhotos({"fpath": fpath}))

    yield Await(jobs)


import logging

logging.basicConfig(level=logging.INFO, force=True)
logging.getLogger("PIL").setLevel(logging.WARNING)

job_registry = SQLiteJobRegistry("mirror_jobs.db")
context = MemoryContext(
    scope=LocalScope(
        dependencies=[ConcurrencyLimit],
        jobs=[ComputeContrastingGrey, ComputeMosaic, UploadPhoto, FindMissingPhotos, UploadMedia]),
    job_registry=job_registry,
)

start = UploadMedia({"force_recompute_grey": False, "force_recompute_mosaic": False, "force_upload_images": False})

for event in LocalWorkflow(context, max_workers=15).run(start):
    print(event)
