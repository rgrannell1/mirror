"""Read and store Wikidata taxonomy data."""

from mirror.commons.config import DATABASE_PATH
from mirror.data.wikidata import WikidataModel
from mirror.services.database import SqliteDatabase


def read_entity(qid: str) -> WikidataModel | None:
    """Read one cached Wikidata entity."""
    with SqliteDatabase(DATABASE_PATH) as db:
        return db.wikidata_table().get_by_id(qid)


def store_entity(qid: str, data: dict) -> WikidataModel:
    """Store and return one Wikidata entity."""
    with SqliteDatabase(DATABASE_PATH) as db:
        db.wikidata_table().add(qid, data)
    return WikidataModel(qid=qid, data=data)


def store_binomial_qid(binomial: str, qid: str | None) -> None:
    """Store one binomial to Wikidata QID mapping."""
    with SqliteDatabase(DATABASE_PATH) as db:
        db.binomials_wikidata_id_table().add(binomial, qid)


def list_unchained_binomials(db: SqliteDatabase) -> list[tuple[str, str]]:
    """Return binomials that have a QID but no stored taxon chain."""
    chained = db.taxon_chains_table().list_binomials()
    return [
        (binomial, qid)
        for binomial, qid in db.binomials_wikidata_id_table().list()
        if qid and binomial not in chained
    ]


def list_pending_chains() -> list[tuple[str, str]]:
    """Return all binomials that need a stored taxon chain."""
    with SqliteDatabase(DATABASE_PATH) as db:
        return list_unchained_binomials(db)


def store_chain(binomial: str, rows: list[tuple[str, str, str]]) -> None:
    """Store one binomial's taxon chain."""
    with SqliteDatabase(DATABASE_PATH) as db:
        chains = db.taxon_chains_table()
        for row in rows:
            chains.add(binomial, row)
