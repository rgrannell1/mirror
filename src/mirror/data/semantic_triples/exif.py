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


def exif_field_triples(
    source: str, exif, relations: tuple[str, ...]
) -> Iterator[SemanticTriple]:
    """Publish selected scalar fields from one EXIF row."""
    for relation in relations:
        yield SemanticTriple(source=source, relation=relation, target=getattr(exif, relation))


def exif_dimension_triples(source: str, exif) -> Iterator[SemanticTriple]:
    """Publish image dimensions when both dimensions exist."""
    if not exif.width or not exif.height:
        return

    yield SemanticTriple(source=source, relation="width", target=exif.width)
    yield SemanticTriple(source=source, relation="height", target=exif.height)


def exif_row_triples(source: str, exif, camera_models: set[str]) -> Iterator[SemanticTriple]:
    """Publishable triples for one EXIF row."""
    yield from exif_field_triples(source, exif, ("f_stop", "focal_length"))

    if exif.model:
        yield from exif_camera_triples(source, exif, camera_models)

    yield from exif_field_triples(source, exif, ("exposure_time", "iso"))
    yield from exif_dimension_triples(source, exif)


class ExifTriplesReader:
    """Stored EXIF rows → triples (file-side reader is models.exif.ExifReader)."""

    @staticmethod
    def read(db: "SqliteDatabase") -> Iterator[SemanticTriple]:
        camera_models: set[str] = set()

        for exif in db.exif_table().list():
            source = f"urn:ró:photo:{deterministic_hash_str(exif.fpath)}"
            yield from exif_row_triples(source, exif, camera_models)
