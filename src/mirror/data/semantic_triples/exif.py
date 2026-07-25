"""EXIF rows in SQLite → semantic triples for publish."""

from typing import TYPE_CHECKING, Iterator

from mirror.commons.utils import deterministic_hash_str
from mirror.data.types import SemanticTriple

if TYPE_CHECKING:
    from mirror.services.database import SqliteDatabase


def exif_camera_triples(source: str, exif, camera_models: set[str]) -> Iterator[SemanticTriple]:
    """Camera triples for one EXIF row, naming each camera the first time it is seen."""
    camera_urn = f"urn:ró:camera:{exif.model.lower().replace(' ', '-')}"

    if camera_urn not in camera_models:
        camera_models.add(camera_urn)
        yield SemanticTriple(camera_urn, "name", exif.model)

    yield SemanticTriple(
        source=source,
        relation="model",
        target=camera_urn,
    )


def exif_row_triples(source: str, exif, camera_models: set[str]) -> Iterator[SemanticTriple]:
    """Publishable triples for one EXIF row."""
    yield SemanticTriple(
        source=source,
        relation="f_stop",
        target=exif.f_stop,
    )

    yield SemanticTriple(
        source=source,
        relation="focal_length",
        target=exif.focal_length,
    )

    if exif.model:
        yield from exif_camera_triples(source, exif, camera_models)

    yield SemanticTriple(
        source=source,
        relation="exposure_time",
        target=exif.exposure_time,
    )

    yield SemanticTriple(
        source=source,
        relation="iso",
        target=exif.iso,
    )

    if exif.width and exif.height:
        yield SemanticTriple(
            source=source,
            relation="width",
            target=exif.width,
        )

        yield SemanticTriple(
            source=source,
            relation="height",
            target=exif.height,
        )


class ExifTriplesReader:
    """Stored EXIF rows → triples (file-side reader is models.exif.ExifReader)."""

    @staticmethod
    def read(db: "SqliteDatabase") -> Iterator[SemanticTriple]:
        camera_models: set[str] = set()

        for exif in db.exif_table().list():
            source = f"urn:ró:photo:{deterministic_hash_str(exif.fpath)}"
            yield from exif_row_triples(source, exif, camera_models)
