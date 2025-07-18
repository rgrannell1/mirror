"""
mirror URNs are of the form

urn:ró:<noun>:<id>?<prop>=<value>...

This file includes classes for converting between Things (id + type + properties) and
representations (URNs). It also includes classes for reading old photo answers into this format, to
help migration into the

    photo-metadata.md <===> database

mapping. It'll output them to the photo-markdown file as URNs
"""

from typing import Iterator, Protocol
import urllib.parse

from src.constants import URN_PREFIX
from src.database import SqliteDatabase


class Things:
    """Manage things (ID'able objects that appear in my media)"""

    @classmethod
    def is_urn(cls, value: str) -> bool:
        """Check if a value is a valid URN"""
        return value.startswith(URN_PREFIX)

    @classmethod
    def from_urn(cls, urn: str) -> dict:
        if not urn.startswith(URN_PREFIX):
            raise ValueError(f"Invalid URN format: must start with '{URN_PREFIX}', got '{urn}'")

        remainder = urn[7:]
        if "?" in remainder:
            main_part, query_part = remainder.split("?", 1)
            qs = dict(urllib.parse.parse_qsl(query_part))
        else:
            main_part = remainder
            qs = {}

        if ":" not in main_part:
            raise ValueError(f"Invalid URN format: missing noun:id separator, got '{urn}'")

        noun, id_part = main_part.split(":", 1)

        if not noun:
            raise ValueError(f"Invalid URN format: empty noun, got '{urn}'")
        if not id_part:
            raise ValueError(f"Invalid URN format: empty id, got '{urn}'")

        return {"type": noun, "id": id_part, **qs}

    @classmethod
    def to_urn(cls, thing: dict) -> str:
        base_urn = f"{URN_PREFIX}{thing['type']}:{thing['id']}"

        props = {key: val for key, val in thing.items() if key not in ("type", "id")}

        if props:
            query_string = urllib.parse.urlencode(props)
            return f"{base_urn}?{query_string}"

        return base_urn


class ThingsReader(Protocol):
    def read(self, db: SqliteDatabase) -> Iterator[tuple[str, dict]]: ...
