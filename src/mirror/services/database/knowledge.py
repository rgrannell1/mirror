"""Geonames, Wikidata, and binomial reference tables."""

import json
import sqlite3
from typing import Iterator, Optional

from mirror.commons.tables import BINOMIALS_WIKIDATA_ID_TABLE, GEONAME_TABLE, WIKIDATA_TABLE
from mirror.data.geoname import GeonameModel
from mirror.data.wikidata import WikidataModel


class GeonameTable:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn
        self.conn.execute(GEONAME_TABLE)

    def add(self, id: str, data: dict) -> None:
        self.conn.execute(
            "insert or replace into geonames (id, data) values (?, ?)",
            (id, json.dumps(data)),
        )
        self.conn.commit()

    def has(self, id: str) -> bool:
        return bool(self.conn.execute("select 1 from geonames where id = ?", (id,)).fetchone())

    def list(self) -> Iterator[GeonameModel]:
        query = "select id, data from geonames"

        for row in self.conn.execute(query):
            yield GeonameModel.from_row(row)


class WikidataTable:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn
        self.conn.execute(WIKIDATA_TABLE)

    def add(self, id: str, data: dict | None) -> None:
        self.conn.execute(
            "insert or replace into wikidata (id, data) values (?, ?)",
            (id, json.dumps(data) if data else None),
        )
        self.conn.commit()

    def has(self, id: str) -> bool:
        return bool(self.conn.execute("select 1 from wikidata where id = ?", (id,)).fetchone())

    def get_by_id(self, id: str) -> Optional[WikidataModel]:
        query = "select id, data from wikidata where id = ?"

        for row in self.conn.execute(query, (id,)):
            return WikidataModel.from_row(row)

        return None

    def list(self) -> Iterator[WikidataModel]:
        query = "select id, data from wikidata"

        for row in self.conn.execute(query):
            yield WikidataModel.from_row(row)


class BinomialsWikidataIdTable:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn
        self.conn.execute(BINOMIALS_WIKIDATA_ID_TABLE)

    def add(self, binomial: str, qid: Optional[str]) -> None:
        self.conn.execute(
            "insert or replace into binomials_wikidata_id (binomial, qid) values (?, ?)",
            (binomial, qid),
        )
        self.conn.commit()

    def has(self, binomial: str) -> bool:
        return bool(self.conn.execute("select 1 from binomials_wikidata_id where binomial = ?", (binomial,)).fetchone())

    def get_binomial(self, qid: str) -> Optional[str]:
        """Given a WikiData ID, get the binomial"""
        query = "select binomial from binomials_wikidata_id where qid = ?"

        for row in self.conn.execute(query, (qid,)):
            return row[0]

        return None

    def list(self) -> Iterator[tuple[str, str]]:
        query = "select binomial, qid from binomials_wikidata_id"

        yield from self.conn.execute(query)
