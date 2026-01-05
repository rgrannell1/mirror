from __future__ import annotations

from typing import Generator, Iterator, TypedDict

from mirror.config import DATABASE_PATH
from mirror.database import SqliteDatabase
from mirror.encoder import PhotoEncoder

from zahir import (
    job,
    Await,
    Context,
    LocalScope,
    SQLiteJobRegistry,
    MemoryContext,
    LocalWorkflow,
    WorkflowOutputEvent,
)


class PhotoJobInput(TypedDict):
    fpath: str


class UploadOpts(TypedDict):
    force_recompute_grey: bool
    force_recompute_mosaic: bool


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


def list_photos_without_upload(db: SqliteDatabase) -> Iterator[str]:
    photos = db.photos_table()
    return iter([])


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
    dependencies={},
) -> Iterator[None]:
    fpath = input["fpath"]

    db = SqliteDatabase(DATABASE_PATH)
    encoded_photos_table = db.encoded_photos_table()

    v2 = PhotoEncoder.encode_image_colours(fpath)
    v2_content = "".join(v2)

    encoded_photos_table.add(fpath, v2_content, "thumbnail_mosaic", "custom")

    return iter(())


@job()
def UploadMedia(
    context: Context,
    input: UploadOpts,
    dependencies={},
) -> Generator[Await | WorkflowOutputEvent]:
    db = SqliteDatabase(DATABASE_PATH)

    force_recompute_grey = input.get("force_recompute_grey", False)
    force_recompute_mosaic = input.get("force_recompute_mosaic", False)

    jobs = []

    for fpath in list_photos_without_contrasting_grey(db, force_recompute_grey):
        jobs.append(ComputeContrastingGrey({"fpath": fpath}))

    for fpath in list_photos_without_mosaic(db, force_recompute_mosaic):
        jobs.append(ComputeMosaic({"fpath": fpath}))

    for fpath in list_photos_without_upload(db):
        ...

    yield Await(jobs)

job_registry = SQLiteJobRegistry("mirror_jobs.db")
context = MemoryContext(scope=LocalScope.from_module(), job_registry=job_registry)

start = UploadMedia({"force_recompute_grey": False, "force_recompute_mosaic": True})

for event in LocalWorkflow(context, max_workers=15).run(start):
    print(event)