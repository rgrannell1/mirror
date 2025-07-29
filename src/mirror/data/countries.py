from typing import Iterator

from mirror.data.types import SemanticTriple


class CountriesReader:
    """Read location information from cached geonames results"""

    def read(self, db: "SqliteDatabase") -> Iterator[SemanticTriple]: ...
