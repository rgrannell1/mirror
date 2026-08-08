"""Tests for taxon (genus, family, order) cover selection."""

from mirror.data.semantic_triples.photos import CoverCandidate
from mirror.data.semantic_triples.taxa import (
    best_taxon_cover,
    group_taxon_candidates,
    pool_taxon_candidate,
    subject_taxon_map,
)
from mirror.services.database import SqliteDatabase


def make(fpath: str, **overrides) -> CoverCandidate:
    """Build a candidate with neutral defaults."""
    fields = {
        "is_explicit": 0,
        "rating_rank": 0,
        "wild_rank": 1,
        "single_subject": 0,
        "has_person": 0,
        "fill": None,
        "species": "",
    }
    fields.update(overrides)
    return CoverCandidate(fpath=fpath, **fields)


def test_pool_taxon_candidate() -> None:
    """Proves pooling drops the explicit trump and tags the species URN."""
    pooled = pool_taxon_candidate(make("a", is_explicit=1), "urn:ró:bird:alca-torda")

    assert pooled.is_explicit == 0
    assert pooled.species == "urn:ró:bird:alca-torda"


SELECTION_CASES = [
    (
        "a direct taxon assignment beats a higher-rated pooled photo",
        [make("a", rating_rank=5, species="urn:ró:bird:a"), make("b", is_explicit=1)],
        "b",
    ),
    (
        "a full tie between species resolves alphabetically",
        [
            make("a", rating_rank=3, species="urn:ró:bird:fratercula-arctica"),
            make("b", rating_rank=3, species="urn:ró:bird:alca-torda"),
        ],
        "b",
    ),
    (
        "rating still beats the alphabetical tie-break",
        [
            make("a", rating_rank=4, species="urn:ró:bird:fratercula-arctica"),
            make("b", rating_rank=3, species="urn:ró:bird:alca-torda"),
        ],
        "a",
    ),
    (
        "tiny subjects lose to a filled photo from another species",
        [
            make("a", rating_rank=5, fill=0.01, species="urn:ró:bird:alca-torda"),
            make("b", rating_rank=1, fill=0.2, species="urn:ró:bird:uria-aalge"),
        ],
        "b",
    ),
]


def test_taxon_cover_selection() -> None:
    """Proves taxon covers rank by the thing key, ties broken by species name."""
    for label, candidates, expected in SELECTION_CASES:
        best = best_taxon_cover(candidates)
        assert best is not None and best.fpath == expected, label


def test_taxon_person_rule() -> None:
    """Proves a taxon whose every photo has a person gets no cover."""
    assert best_taxon_cover([make("a", has_person=1), make("b", has_person=1)]) is None


def make_taxa_db() -> SqliteDatabase:
    """Build a database with a photographed razorbill and its taxon chain."""
    db = SqliteDatabase(":memory:")
    db.photo_metadata_table()
    db.phashes_table()
    db.photos_table()
    chains = db.taxon_chains_table()
    fpath = "/album/Published/a.jpg"
    db.conn.execute("insert into photos values (?, '/album/Published')", (fpath,))
    db.conn.execute("insert into phashes values (?, 'h1')", (fpath,))
    db.conn.execute(
        "insert into photo_metadata_table (phash, src_type, relation, target)"
        " values ('h1', 'photo', 'subject', 'urn:ró:bird:alca-torda')"
    )
    db.conn.commit()
    chains.add("Alca torda", ("genus", "Q2", "Alca"))
    chains.add("Alca torda", ("family", "Q3", "Alcidae"))
    chains.add("Alca torda", ("class", "Q5", "Aves"))
    return db


def test_subject_taxon_map() -> None:
    """Proves subjects map to their published-rank taxon URNs only."""
    with make_taxa_db() as db:
        assert subject_taxon_map(db) == {
            "urn:ró:bird:alca-torda": ["urn:ró:family:alcidae", "urn:ró:genus:alca"]
        }


def test_group_taxon_candidates() -> None:
    """Proves species rows pool under each taxon and taxon rows stay direct."""
    taxa_of = {"urn:ró:bird:alca-torda": ["urn:ró:family:alcidae", "urn:ró:genus:alca"]}
    razorbill = "urn:ró:bird:alca-torda"
    species_row = ("/a.jpg", "p1", razorbill, "⭐", razorbill, "subject")
    assigned_row = ("/b.jpg", "p2", "urn:ró:family:alcidae", "⭐", "", "cover")
    unrelated_row = ("/c.jpg", "p3", "urn:ró:place:paris", "⭐", "", "location")

    groups = group_taxon_candidates([species_row, assigned_row, unrelated_row], {}, {}, taxa_of)

    assert set(groups) == {"urn:ró:family:alcidae", "urn:ró:genus:alca"}
    family_group = groups["urn:ró:family:alcidae"]
    assert [candidate.fpath for candidate in family_group] == ["/a.jpg", "/b.jpg"]
    assert family_group[0].species == razorbill
    assert family_group[1].is_explicit == 1
    assert groups["urn:ró:genus:alca"][0].fpath == "/a.jpg"
