"""
mirror ARNs are of the form

arn:ró:<noun>:<id>?<prop>=<value>...

This file includes classes for converting between Things (id + type + properties) and
representations (ARNs). It also includes classes for reading old photo answers into this format, to
help migration into the

    photo-metadata.md <===> database

mapping. It'll output them to the photo-markdown file as ARNs
"""

from typing import Iterator, Protocol
import urllib.parse

from src.constants import ARN_PREFIX
from src.database import SqliteDatabase


class Things:
    """Manage things (ID'able objects that appear in my media)"""

    @classmethod
    def from_arn(cls, arn: str) -> dict:
        if not arn.startswith(ARN_PREFIX):
            raise ValueError(f"Invalid ARN format: must start with '{ARN_PREFIX}', got '{arn}'")

        remainder = arn[7:]
        if "?" in remainder:
            main_part, query_part = remainder.split("?", 1)
            qs = dict(urllib.parse.parse_qsl(query_part))
        else:
            main_part = remainder
            qs = {}

        if ":" not in main_part:
            raise ValueError(f"Invalid ARN format: missing noun:id separator, got '{arn}'")

        noun, id_part = main_part.split(":", 1)

        if not noun:
            raise ValueError(f"Invalid ARN format: empty noun, got '{arn}'")
        if not id_part:
            raise ValueError(f"Invalid ARN format: empty id, got '{arn}'")

        return {"type": "noun", "id": id_part, **qs}

    @classmethod
    def to_arn(cls, thing: dict) -> str:
        base_arn = f"{ARN_PREFIX}{thing['type']}:{thing['id']}"

        props = {key: val for key, val in thing.items() if key not in ("type", "id")}

        if props:
            query_string = urllib.parse.urlencode(props)
            return f"{base_arn}?{query_string}"

        return base_arn


class ThingsReader(Protocol):
    def read(self, db: SqliteDatabase) -> Iterator[tuple[str, dict]]:
        ...

class AnswersBirdsReader(ThingsReader):
    """Construct answers into information about birds in photos"""

    def read(self, db: SqliteDatabase) -> Iterator[tuple[str, dict]]:

        phashes = db.phashes_table()
        relations = list(db.photo_metadata_table().list())

        photos: dict[str, dict] = {  }

        for row in relations:
            if row.relation == "Wildlife" and row.target == "Bird":
                if row.fpath not in photos:
                    photos[row.fpath] = {
                        "id": "unknown",
                        "type": "bird",
                    }

        for row in relations:
            if row.relation == "bird_binomial":
                if row.fpath not in photos:
                    photos[row.fpath] = {
                        "type": "bird",
                    }

                    photos[row.fpath]["id"] = row.target.replace(' ', '-').lower()

        for row in relations:
            if row.relation == "living_conditions":
                if row.fpath in photos:
                    photos[row.fpath]["context"] = row.target.lower()

        for fpath, thing in photos.items():
            phash = phashes.phash_from_fpath(fpath)

            if phash is None:
                continue

            yield phash, thing


class AnswersPlaneReader(ThingsReader):
    """Construct answers into information about planes in photos"""

    def read(self, db: SqliteDatabase) -> Iterator[tuple[str, dict]]:
        phashes = db.phashes_table()
        relations = list(db.photo_metadata_table().list())

        photos: dict[str, dict] = {}

        for row in relations:
            if row.relation == "vehicle" and row.target == "Plane":
                if row.fpath not in photos:
                    photos[row.fpath] = {
                        "id": "unknown",
                        "type": "plane",
                    }

        for row in relations:
            if row.relation == "plane_model":
                if row.fpath not in photos:
                    photos[row.fpath] = {
                        "type": "plane"
                    }

                photos[row.fpath]["id"] = urllib.parse.quote(row.target)

        for fpath, thing in photos.items():
            phash = phashes.phash_from_fpath(fpath)

            if phash is None:
                continue

            yield phash, thing