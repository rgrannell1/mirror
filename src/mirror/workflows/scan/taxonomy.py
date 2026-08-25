"""Walk Wikidata parent-taxon chains for photo binomials and store rank rows."""

from collections.abc import Generator
from typing import Any

from zahir import JobContext, await_all, rate_limit_dependency

from mirror.commons.constants import TAXON_CHAIN_MAX_DEPTH, KnownWikiProperties
from mirror.data.wikidata import WikidataModel
from mirror.services.taxonomy_store import (
    list_pending_chains,
    read_entity,
    store_binomial_qid,
    store_chain,
    store_entity,
)
from mirror.services.wikidata_lookup import (
    WikidataLookupError,
    fetch_entity_data,
    find_binomial_qid,
)
from mirror.workflows.output import workflow_output

# Shared gate name: every Wikidata fetch in the workflow waits on the same limiter.
WIKIDATA_RATE_LIMIT_NAME = "wikidata"

# Design rule: at most one external request per second.
WIKIDATA_MIN_SECONDS = 1.0


def fetch_entity(qid: str) -> Generator[Any, Any, WikidataModel | None]:
    """Read an entity from the wikidata cache; fetch rate-limited on a miss.

    Label-less cached entities count as misses: they predate mul-label fetching,
    and refetching heals the cache.
    """
    cached = read_entity(qid)
    if cached and cached.data and cached.find_label():
        return cached

    yield from rate_limit_dependency(WIKIDATA_RATE_LIMIT_NAME, WIKIDATA_MIN_SECONDS)
    data = fetch_entity_data(qid)
    if data is None:
        return None

    return store_entity(qid, data)


def resolve_rank(entity: WikidataModel) -> Generator[Any, Any, str]:
    """The lower-case English rank label of a taxon entity, or '' when rankless."""
    rank_qid = entity.find_claim_target(KnownWikiProperties.TAXON_RANK)
    if not rank_qid:
        return ""

    rank_entity = yield from fetch_entity(rank_qid)
    if not rank_entity:
        return ""

    return (rank_entity.find_label() or "").lower()


def chain_row(entity: WikidataModel, rank: str) -> tuple[str, str, str] | None:
    """A (rank, qid, label) row for a taxon, or None when rankless or unnamed."""
    label = entity.find_label() or ""
    if rank and label:
        return (rank, entity.qid, label)
    return None


def walk_taxon_chain(qid: str) -> Generator[Any, Any, list[tuple[str, str, str]]]:
    """Collect (rank, qid, label) up the parent-taxon chain, first row per rank."""
    rows: dict[str, tuple[str, str, str]] = {}
    current = qid

    for _ in range(TAXON_CHAIN_MAX_DEPTH):
        entity = yield from fetch_entity(current)
        if not entity:
            break

        rank = yield from resolve_rank(entity)
        row = chain_row(entity, rank)
        if row:
            rows.setdefault(rank, row)

        current = entity.find_claim_target(KnownWikiProperties.PARENT_TAXON)
        if not current:
            break

    return list(rows.values())


def lookup_binomial(ctx: JobContext, input: dict) -> Generator[Any, Any, dict]:
    """Find and store the Wikidata QID for one binomial, rate-limited.

    Failed lookups store a null QID, and stay listed for retry on later runs.
    """
    binomial = input["binomial"]
    yield from rate_limit_dependency(WIKIDATA_RATE_LIMIT_NAME, WIKIDATA_MIN_SECONDS)
    try:
        qid = find_binomial_qid(binomial)
    except WikidataLookupError as err:
        yield workflow_output(f"wikidata lookup failed for {binomial}: {err}")
        return {"found": False}

    store_binomial_qid(binomial, qid or None)
    entity = None
    if qid:
        entity = yield from fetch_entity(qid)

    return {"found": entity is not None}
    yield


def chain_binomial(ctx: JobContext, input: dict) -> Generator[Any, Any, dict]:
    """Walk and store the taxon chain for one binomial.

    Failures are contained: an exception chains nothing for this binomial and
    the next run retries it, without failing the sibling jobs.
    """
    binomial = input["binomial"]

    try:
        rows = yield from walk_taxon_chain(input["qid"])
        store_chain(binomial, rows)
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
    pending = list_pending_chains()

    jobs = [
        ctx.scope.chain_binomial({"binomial": binomial, "qid": qid}) for binomial, qid in pending
    ]
    results = yield await_all(jobs)

    chained = sum(1 for result in results if result["chained"])
    return {"chained": chained}
    yield
