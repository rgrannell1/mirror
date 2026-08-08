"""Walk Wikidata parent-taxon chains for photo binomials and store rank rows."""

from collections.abc import Generator
from typing import Any

import requests
from zahir import JobContext, await_all, rate_limit_dependency

from mirror.commons.config import DATABASE_PATH
from mirror.commons.constants import TAXON_CHAIN_MAX_DEPTH, KnownWikiProperties
from mirror.data.wikidata import WikidataClient, WikidataModel
from mirror.services.database import SqliteDatabase
from mirror.workflows.output import workflow_output

# Shared gate name: every Wikidata fetch in the workflow waits on the same limiter.
WIKIDATA_RATE_LIMIT_NAME = "wikidata"

# Design rule: at most one external request per second.
WIKIDATA_MIN_SECONDS = 1.0


def fetch_entity(
    db: SqliteDatabase, client: WikidataClient, qid: str
) -> Generator[Any, Any, WikidataModel | None]:
    """Read an entity from the wikidata cache; fetch rate-limited on a miss.

    Label-less cached entities count as misses: they predate mul-label fetching,
    and refetching heals the cache.
    """
    cached = db.wikidata_table().get_by_id(qid)
    if cached and cached.data and cached.find_label():
        return cached

    yield from rate_limit_dependency(WIKIDATA_RATE_LIMIT_NAME, WIKIDATA_MIN_SECONDS)
    data = client.get_by_id(qid)
    if data is None:
        return None

    db.wikidata_table().add(qid, data)
    return WikidataModel(qid=qid, data=data)


def resolve_rank(
    db: SqliteDatabase, client: WikidataClient, entity: WikidataModel
) -> Generator[Any, Any, str]:
    """The lower-case English rank label of a taxon entity, or '' when rankless."""
    rank_qid = entity.find_claim_target(KnownWikiProperties.TAXON_RANK)
    if not rank_qid:
        return ""

    rank_entity = yield from fetch_entity(db, client, rank_qid)
    if not rank_entity:
        return ""

    return (rank_entity.find_label() or "").lower()


def chain_row(entity: WikidataModel, rank: str) -> tuple[str, str, str] | None:
    """A (rank, qid, label) row for a taxon, or None when rankless or unnamed."""
    label = entity.find_label() or ""
    if rank and label:
        return (rank, entity.qid, label)
    return None


def walk_taxon_chain(
    db: SqliteDatabase, client: WikidataClient, qid: str
) -> Generator[Any, Any, list[tuple[str, str, str]]]:
    """Collect (rank, qid, label) up the parent-taxon chain, first row per rank."""
    rows: dict[str, tuple[str, str, str]] = {}
    current = qid

    for _ in range(TAXON_CHAIN_MAX_DEPTH):
        entity = yield from fetch_entity(db, client, current)
        if not entity:
            break

        rank = yield from resolve_rank(db, client, entity)
        row = chain_row(entity, rank)
        if row:
            rows.setdefault(rank, row)

        current = entity.find_claim_target(KnownWikiProperties.PARENT_TAXON)
        if not current:
            break

    return list(rows.values())


def list_unchained_binomials(db: SqliteDatabase) -> list[tuple[str, str]]:
    """Binomials that have a QID but no stored taxon chain."""
    chained = db.taxon_chains_table().list_binomials()

    pending = []
    for binomial, qid in db.binomials_wikidata_id_table().list():
        if qid and binomial not in chained:
            pending.append((binomial, qid))
    return pending


def lookup_binomial(ctx: JobContext, input: dict) -> Generator[Any, Any, dict]:
    """Find and store the Wikidata QID for one binomial, rate-limited.

    Failed lookups store a null QID, and stay listed for retry on later runs.
    """
    binomial = input["binomial"]
    client = WikidataClient()

    yield from rate_limit_dependency(WIKIDATA_RATE_LIMIT_NAME, WIKIDATA_MIN_SECONDS)
    try:
        qid = client.find_qid_by_binomial(binomial)
    except requests.RequestException as err:
        yield workflow_output(f"wikidata lookup failed for {binomial}: {err}")
        return {"found": False}

    entity = None
    with SqliteDatabase(DATABASE_PATH) as db:
        db.binomials_wikidata_id_table().add(binomial, qid or None)
        if qid:
            entity = yield from fetch_entity(db, client, qid)

    return {"found": entity is not None}
    yield


def chain_binomial(ctx: JobContext, input: dict) -> Generator[Any, Any, dict]:
    """Walk and store the taxon chain for one binomial.

    Failures are contained: an exception chains nothing for this binomial and
    the next run retries it, without failing the sibling jobs.
    """
    client = WikidataClient()
    binomial = input["binomial"]

    try:
        with SqliteDatabase(DATABASE_PATH) as db:
            rows = yield from walk_taxon_chain(db, client, input["qid"])
            chains = db.taxon_chains_table()
            for rank_row in rows:
                chains.add(binomial, rank_row)
    except Exception as err:  # noqa: BLE001
        yield workflow_output(f"taxon chain failed for {binomial}: {err}")
        return {"chained": False}

    return {"chained": bool(rows)}
    yield


def taxonomy_scan(ctx: JobContext, input: dict) -> Generator[Any, Any, dict]:
    """Store the Wikidata rank chain for each binomial without one.

    One sub-job per binomial via await_all. Idempotent: chained binomials are
    skipped, and entity fetches hit the shared wikidata cache before any
    request. Cache misses across all jobs share the one-per-second rate gate.
    """
    with SqliteDatabase(DATABASE_PATH) as db:
        pending = list_unchained_binomials(db)

    jobs = [
        ctx.scope.chain_binomial({"binomial": binomial, "qid": qid}) for binomial, qid in pending
    ]
    results = yield await_all(jobs)

    chained = sum(1 for result in results if result["chained"])
    return {"chained": chained}
    yield
