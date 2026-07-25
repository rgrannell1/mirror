import json
from typing import TYPE_CHECKING, Iterator

import tomllib

if TYPE_CHECKING:
    from mirror.services.database import SqliteDatabase
from mirror.data.types import SemanticTriple


def read_things_unesco_ids(things_file: str) -> set[str]:
    """UNESCO site ids referenced by places in things.toml."""
    unesco_ids = set()

    with open(things_file, "rb") as conn:
        places = tomllib.load(conn)

    for place in places["places"]:
        unesco_urn = place.get("unesco_id")

        if unesco_urn:
            unesco_ids.add(unesco_urn.split(":")[-1])

    return unesco_ids


class UnescoReader:
    things_file: str
    data_file: str

    def __init__(self, things_file: str = "things.toml", data_file: str = "src/data/whc001.json"):
        self.things_file = things_file
        self.data_file = data_file

    def read(self, db: "SqliteDatabase") -> Iterator[SemanticTriple]:
        unesco_ids = read_things_unesco_ids(self.things_file)

        with open(self.data_file, encoding="utf-8") as fh:
            unesco_data = json.load(fh)

        for unesco_site in unesco_data:
            id_no = unesco_site["id_no"]
            if id_no not in unesco_ids:
                continue

            urn = f"urn:ró:unesco:{id_no}"

            yield SemanticTriple(
                source=urn,
                relation="name",
                target=unesco_site["name_en"],
            )

            yield SemanticTriple(
                source=urn,
                relation="longitude",
                target=unesco_site["coordinates"]["lon"],
            )

            yield SemanticTriple(
                source=urn,
                relation="latitude",
                target=unesco_site["coordinates"]["lat"],
            )
