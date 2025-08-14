from typing import Iterator
from mirror.data.types import SemanticTriple
from mirror.utils import deterministic_hash_str


class ExifReader:
    def read(self, db: "SqliteDatabase") -> Iterator[SemanticTriple]:
        camera_models = set()

        for exif in db.exif_table().list():
            source = f"urn:ró:photo:{deterministic_hash_str(exif.fpath)}"

            parts = exif.created_at.split(" ") if exif.created_at else ""
            date = parts[0].replace(":", "/")
            created_at = f"{date} {parts[1]}"

            yield SemanticTriple(
                source=source,
                relation="created_at",
                target=created_at,
            )

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
                camera_urn = f"urn:ró:camera:{exif.model.lower().replace(' ', '-')}"

                if camera_urn not in camera_models:
                    camera_models.add(camera_urn)
                    yield SemanticTriple(camera_urn, "name", exif.model)

                yield SemanticTriple(
                    source=source,
                    relation="model",
                    target=camera_urn,
                )

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
