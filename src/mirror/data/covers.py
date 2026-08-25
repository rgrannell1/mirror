"""Shared cover selection for triple publication, upload gating, and social cards.

One algorithm chooses each thing's cover photo. The selection is cached with
funes, keyed on a content hash of its inputs, so a changed rating, scan, or
configuration busts the cache automatically.
"""

from typing import TYPE_CHECKING, Iterator, NamedTuple

from funes import SqliteStore

from mirror.commons.config import FUNES_CACHE_PATH
from mirror.commons.constants import (
    COVER_CACHE_MAX_ENTRIES,
    COVER_MIN_SUBJECT_FILL,
    PERSON_URN_PREFIX,
    PUBLISHED_TAXON_RANKS,
)
from mirror.commons.utils import deterministic_hash_str
from mirror.data.semantic_triples.photos import (
    LISTING_COVER_QUERY,
    THING_COVER_QUERY,
    CoverCandidate,
    best_box_scans,
    cover_sort_key,
    eligible_candidates,
    feature_cover_candidates,
    genre_priority_sql,
    genre_then_rating,
    make_candidate,
    map_place_photos,
    person_free,
    photo_areas,
    rating_rank_sql,
    subject_type_of,
)
from mirror.data.semantic_triples.taxa import (
    best_taxon_cover,
    group_taxon_candidates,
    subject_taxon_map,
)
from mirror.data.things import (
    genre_cover_priorities,
    place_feature_to_places,
    rating_ranks,
    unlisted_types,
)
from mirror.data.types import SemanticTriple

if TYPE_CHECKING:
    from mirror.services.database import SqliteDatabase


class CoverInputs(NamedTuple):
    """Everything the cover-selection algorithm reads, gathered for hashing and replay."""

    thing_rows: tuple
    scans: dict
    areas: dict
    taxa_of: dict
    listing_rows: tuple
    feature_to_places: dict
    place_photos: dict
    params: tuple


class CoverSelection(NamedTuple):
    """Chosen cover fpaths, keyed by the URN of the thing each photo covers."""

    things: dict[str, str]
    taxa: dict[str, str]
    listings: dict[str, str]
    features: dict[str, str]


def read_listing_rows(db: "SqliteDatabase") -> tuple:
    """Run the SQL-side listing cover selection, returning (fpath, listing_type) rows."""
    excluded = tuple(sorted(unlisted_types()))
    query = LISTING_COVER_QUERY.format(
        excluded=",".join("?" for _ in excluded),
        place_genre_order=genre_priority_sql("place", "genre"),
        rating_order=rating_rank_sql("rating"),
    )
    return tuple(db.conn.execute(query, excluded).fetchall())


def algorithm_params() -> tuple:
    """The configured parameters the ranking depends on, for cache busting."""
    return (
        tuple(sorted(rating_ranks().items())),
        tuple(sorted(genre_cover_priorities("place").items())),
        COVER_MIN_SUBJECT_FILL,
    )


def read_cover_inputs(db: "SqliteDatabase") -> CoverInputs:
    """Gather every input of the cover-selection algorithm from the database."""
    feature_to_places = place_feature_to_places()
    place_urns = sorted({urn for urns in feature_to_places.values() for urn in urns})

    return CoverInputs(
        thing_rows=tuple(db.conn.execute(THING_COVER_QUERY).fetchall()),
        scans=best_box_scans(db),
        areas=photo_areas(db),
        taxa_of=subject_taxon_map(db),
        listing_rows=read_listing_rows(db),
        feature_to_places=feature_to_places,
        place_photos=map_place_photos(db, place_urns) if place_urns else {},
        params=algorithm_params(),
    )


def select_thing_covers(inputs: CoverInputs) -> dict[str, str]:
    """Choose one cover fpath per individual thing (bird, place, country, etc.)."""
    groups: dict[str, list[CoverCandidate]] = {}
    for row in inputs.thing_rows:
        thing_urn, candidate = make_candidate(row, inputs.scans, inputs.areas)
        if subject_type_of(thing_urn) in PUBLISHED_TAXON_RANKS:
            continue
        groups.setdefault(thing_urn, []).append(candidate)

    covers: dict[str, str] = {}
    for thing_urn, group in groups.items():
        allowed = person_free(group)
        if not allowed:
            continue

        covers[thing_urn] = max(eligible_candidates(allowed), key=cover_sort_key).fpath
    return covers


def select_taxon_covers(inputs: CoverInputs) -> dict[str, str]:
    """Choose one cover fpath per published taxon (genus, family, order)."""
    groups = group_taxon_candidates(
        list(inputs.thing_rows), inputs.scans, inputs.areas, inputs.taxa_of
    )

    covers: dict[str, str] = {}
    for taxon_urn, group in groups.items():
        best = best_taxon_cover(group)
        if best:
            covers[taxon_urn] = best.fpath
    return covers


def select_feature_covers(inputs: CoverInputs) -> dict[str, str]:
    """Choose one cover fpath per place feature, plus the place_feature listing cover."""
    covers: dict[str, str] = {}
    all_candidates: list[tuple] = []

    for feature_urn, best in feature_cover_candidates(
        inputs.feature_to_places, inputs.place_photos
    ):
        covers[feature_urn] = best[0]
        all_candidates.append(best)

    if all_candidates:
        listing_best = min(all_candidates, key=genre_then_rating)
        covers["urn:ró:listing:place_feature"] = listing_best[0]
    return covers


def select_covers(inputs: CoverInputs) -> CoverSelection:
    """Run the full cover selection over pre-gathered inputs."""
    listings = {
        f"urn:ró:listing:{listing_type}": fpath for fpath, listing_type in inputs.listing_rows
    }

    return CoverSelection(
        things=select_thing_covers(inputs),
        taxa=select_taxon_covers(inputs),
        listings=listings,
        features=select_feature_covers(inputs),
    )


def normalise_inputs(inputs: CoverInputs) -> str:
    """A canonical text form of the inputs, independent of row and dict order."""
    parts = (
        sorted(inputs.thing_rows, key=repr),
        sorted(inputs.scans.items(), key=repr),
        sorted(inputs.areas.items(), key=repr),
        sorted(inputs.taxa_of.items(), key=repr),
        sorted(inputs.listing_rows, key=repr),
        sorted(inputs.feature_to_places.items(), key=repr),
        sorted(inputs.place_photos.items(), key=repr),
        inputs.params,
    )
    return repr(parts)


def cover_inputs_key(*args, **_kwargs) -> str:
    """funes cache key: a content hash of the selection inputs."""
    (inputs,) = args
    return deterministic_hash_str(normalise_inputs(inputs))


def cached_cover_selection(
    db: "SqliteDatabase", cache_path: str = FUNES_CACHE_PATH
) -> CoverSelection:
    """Select covers, reusing the funes-cached result when the inputs are unchanged."""
    inputs = read_cover_inputs(db)
    store = SqliteStore(db_path=cache_path, key=cover_inputs_key, max_size=COVER_CACHE_MAX_ENTRIES)
    with store:
        return store.run(select_covers, inputs)


def cover_pairs(selection: CoverSelection) -> Iterator[tuple[str, str]]:
    """Yield every (thing urn, cover fpath) pair in the selection."""
    for mapping in selection:
        yield from mapping.items()


PERSON_SUBJECT_QUERY = "select fpath from view_photo_metadata_summary where subjects like ?"


def person_photo_fpaths(db: "SqliteDatabase") -> frozenset[str]:
    """Photos with a person subject. These must never become social cards."""
    rows = db.conn.execute(PERSON_SUBJECT_QUERY, (f"%{PERSON_URN_PREFIX}%",))
    return frozenset(fpath for (fpath,) in rows)


def thing_card_pairs(selection: CoverSelection) -> Iterator[tuple[str, str]]:
    """(urn, cover fpath) pairs for thing pages. Listing covers have no thing page."""
    for mapping in (selection.things, selection.taxa, selection.features):
        for thing_urn, fpath in mapping.items():
            if thing_urn.startswith("urn:ró:listing:"):
                continue
            yield thing_urn, fpath


def cover_fpaths(db: "SqliteDatabase", cache_path: str = FUNES_CACHE_PATH) -> frozenset[str]:
    """Every computed cover photo fpath, across things, taxa, listings, and features."""
    selection = cached_cover_selection(db, cache_path)
    return frozenset(fpath for _, fpath in cover_pairs(selection))


class CoversReader:
    """Emits photo cover triples for things, taxa, listings, and place features.

    Emits triples:  urn:ró:photo:<id>  cover  urn:ró:<type>:<id>
    """

    @staticmethod
    def read(db: "SqliteDatabase") -> Iterator[SemanticTriple]:
        selection = cached_cover_selection(db)

        for thing_urn, fpath in cover_pairs(selection):
            photo_urn = f"urn:ró:photo:{deterministic_hash_str(fpath)}"
            yield SemanticTriple(photo_urn, "cover", thing_urn)
