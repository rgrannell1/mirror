"""Publish genus, family, and order triples for each photographed subject."""

from typing import TYPE_CHECKING, Iterator, NamedTuple

from mirror.commons.constants import PUBLISHED_TAXON_RANKS
from mirror.commons.urn import format_mirror_urn
from mirror.commons.utils import deterministic_hash_str
from mirror.data.binomials import binomial_urn_map, normalise_binomial
from mirror.data.semantic_triples.photos import (
    THING_COVER_QUERY,
    CoverCandidate,
    best_box_scans,
    cover_sort_key,
    eligible_candidates,
    make_candidate,
    person_free,
    photo_areas,
    subject_type_of,
)
from mirror.data.types import SemanticTriple

if TYPE_CHECKING:
    from mirror.services.database import SqliteDatabase


class TaxonLink(NamedTuple):
    """One subject's membership of one published-rank taxon."""

    subject_urn: str
    rank: str
    taxon_urn: str
    qid: str
    latin_name: str


def taxon_urn(rank: str, latin_name: str) -> str:
    """The URN for one taxon, e.g. urn:ró:family:gruidae.

    Built from the Latin name: it is stable, unlike common names and labels.
    """
    return format_mirror_urn({"type": rank, "id": latin_name.lower().replace(" ", "-")})


def taxon_common_name(db: "SqliteDatabase", qid: str) -> str | None:
    """The English common name of a taxon (P1843), where Wikidata has one."""
    entity = db.wikidata_table().get_by_id(qid)
    if not entity:
        return None

    return entity.find_common_name()


def taxon_scientific_name(db: "SqliteDatabase", qid: str, fallback: str) -> str:
    """The Latin taxon name (P225). Chain labels can be vernacular; P225 never is."""
    entity = db.wikidata_table().get_by_id(qid)
    if not entity:
        return fallback

    return entity.find_taxon_name() or fallback


def taxon_name_triples(
    db: "SqliteDatabase", scan: tuple[str, str, str]
) -> Iterator[SemanticTriple]:
    """The name triples for one taxon: scientific name, plus any common name."""
    target, qid, latin_name = scan
    yield SemanticTriple(target, "name", latin_name)

    common_name = taxon_common_name(db, qid)
    if common_name:
        yield SemanticTriple(target, "common_name", common_name)


def list_taxon_links(db: "SqliteDatabase") -> Iterator[TaxonLink]:
    """Yield each subject's published-rank taxon memberships, sorted by binomial."""
    urns = binomial_urn_map(db)
    chains = db.taxon_chains_table()

    for binomial in sorted(chains.list_binomials()):
        subject_urn = urns.get(normalise_binomial(binomial))
        if not subject_urn:
            continue

        for rank, qid, label in chains.list_chain(binomial):
            if rank not in PUBLISHED_TAXON_RANKS:
                continue

            latin_name = taxon_scientific_name(db, qid, label)
            yield TaxonLink(subject_urn, rank, taxon_urn(rank, latin_name), qid, latin_name)


class TaxonRelationsReader:
    """Emits:  urn:ró:<type>:<binomial>  genus|family|order  urn:ró:<rank>:<slug>
    urn:ró:<rank>:<slug>  name  <scientific label>
    urn:ró:<rank>:<slug>  common_name  <english common name, where one exists>
    """

    @staticmethod
    def read(db: "SqliteDatabase") -> Iterator[SemanticTriple]:
        named: set[str] = set()

        for link in list_taxon_links(db):
            yield SemanticTriple(link.subject_urn, link.rank, link.taxon_urn)
            if link.taxon_urn not in named:
                named.add(link.taxon_urn)
                yield from taxon_name_triples(db, (link.taxon_urn, link.qid, link.latin_name))


def subject_taxon_map(db: "SqliteDatabase") -> dict[str, list[str]]:
    """Map each subject URN to the published-rank taxon URNs it belongs to."""
    mapping: dict[str, list[str]] = {}
    for link in list_taxon_links(db):
        mapping.setdefault(link.subject_urn, []).append(link.taxon_urn)
    return mapping


def pool_taxon_candidate(candidate: CoverCandidate, species_urn: str) -> CoverCandidate:
    """Rescope a species-level candidate to a taxon group.

    Explicit assignment is scoped to its own target URN, so the trump is
    dropped. The species URN carries the alphabetical tie-break.
    """
    return candidate._replace(is_explicit=0, species=species_urn)


def best_taxon_cover(candidates: list[CoverCandidate]) -> CoverCandidate | None:
    """Pick a taxon's cover: the usual ranking, ties broken by species name."""
    allowed = person_free(candidates)
    if not allowed:
        return None

    by_species = sorted(eligible_candidates(allowed), key=lambda candidate: candidate.species)
    return max(by_species, key=cover_sort_key)


def group_taxon_candidates(
    rows: list[tuple], scans: dict, areas: dict, taxa_of: dict[str, list[str]]
) -> dict[str, list[CoverCandidate]]:
    """Group cover candidates by taxon URN, pooling species photos upward.

    Rows targeting a taxon URN directly (hand assignments) join that taxon's
    group as-is, explicit trump intact.
    """
    groups: dict[str, list[CoverCandidate]] = {}
    for row in rows:
        base_urn, candidate = make_candidate(row, scans, areas)
        if subject_type_of(base_urn) in PUBLISHED_TAXON_RANKS:
            groups.setdefault(base_urn, []).append(candidate)
            continue

        for taxon in taxa_of.get(base_urn, []):
            groups.setdefault(taxon, []).append(pool_taxon_candidate(candidate, base_urn))
    return groups


class TaxonCoverReader:
    """Selects one cover photo per published taxon (genus, family, order).

    Every subject photo of every species under a taxon competes, ranked by the
    thing-cover key. A species' explicit cover loses its trump here: it is
    scoped to the species URN. Hand assignments made directly to a taxon URN
    stay explicit and win. Cross-species ties resolve alphabetically.

    Emits triples:  urn:ró:photo:<id>  cover  urn:ró:<rank>:<slug>
    """

    @staticmethod
    def read(db: "SqliteDatabase") -> Iterator[SemanticTriple]:
        rows = db.conn.execute(THING_COVER_QUERY).fetchall()
        taxa_of = subject_taxon_map(db)
        groups = group_taxon_candidates(rows, best_box_scans(db), photo_areas(db), taxa_of)

        for taxon, group in groups.items():
            best = best_taxon_cover(group)
            if not best:
                continue

            photo_urn = f"urn:ró:photo:{deterministic_hash_str(best.fpath)}"
            yield SemanticTriple(photo_urn, "cover", taxon)
