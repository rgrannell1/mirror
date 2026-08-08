"""Tests for Wikidata taxon-chain walking and storage."""

from mirror.data.semantic_triples.listings import listed_types, listing_entity_triples
from mirror.data.semantic_triples.taxa import TaxonRelationsReader, taxon_name_triples
from mirror.data.wikidata import WikidataModel
from mirror.services.database import SqliteDatabase
from mirror.workflows.scan.taxonomy import list_unchained_binomials, walk_taxon_chain
from mirror.workflows.scan.utils import list_unsaved_binomials


def make_claim(target_qid: str) -> dict:
    """Build one Wikidata claim pointing at an entity."""
    return {"mainsnak": {"datavalue": {"value": {"id": target_qid}}}}


def make_entity(label: str, rank_qid: str = "", parent_qid: str = "") -> dict:
    """Build a minimal Wikidata taxon entity."""
    claims = {}
    if rank_qid:
        claims["P105"] = [make_claim(rank_qid)]
    if parent_qid:
        claims["P171"] = [make_claim(parent_qid)]
    return {"labels": {"en": {"value": label}}, "claims": claims}


def run_generator(generator):
    """Drive a generator that should complete without unanswered effects."""
    try:
        while True:
            generator.send(None)
    except StopIteration as stop:
        return stop.value


def test_find_claim_target() -> None:
    """Proves claim targets parse from entity JSON and absent claims give None."""
    entity = WikidataModel(qid="Q1", data=make_entity("Razorbill", "Qr1", "Q2"))

    assert entity.find_claim_target("P105") == "Qr1"
    assert entity.find_claim_target("P171") == "Q2"
    assert entity.find_claim_target("P9999") is None
    assert WikidataModel(qid="Q1", data=None).find_claim_target("P105") is None


def make_chain_db() -> SqliteDatabase:
    """Preload the wikidata cache with a species → genus → family chain."""
    db = SqliteDatabase(":memory:")
    wikidata = db.wikidata_table()

    wikidata.add("Qr1", make_entity("Species"))
    wikidata.add("Qr2", make_entity("Genus"))
    wikidata.add("Qr3", make_entity("Family"))

    wikidata.add("Q1", make_entity("Alca torda", rank_qid="Qr1", parent_qid="Q2"))
    wikidata.add("Q2", make_entity("Alca", rank_qid="Qr2", parent_qid="Q3"))
    wikidata.add("Q3", make_entity("Alcidae", rank_qid="Qr3"))
    return db


def test_walk_taxon_chain() -> None:
    """Proves the walk collects one lower-cased rank row per ancestor, in order."""
    db = make_chain_db()

    rows = run_generator(walk_taxon_chain(db, None, "Q1"))

    assert rows == [
        ("species", "Q1", "Alca torda"),
        ("genus", "Q2", "Alca"),
        ("family", "Q3", "Alcidae"),
    ]
    db.close()


def test_walk_skips_duplicate_ranks_and_rankless_taxa() -> None:
    """Proves only the first taxon of a rank is kept, and rankless taxa are skipped."""
    db = SqliteDatabase(":memory:")
    wikidata = db.wikidata_table()
    wikidata.add("Qr2", make_entity("Genus"))
    wikidata.add("Q1", make_entity("Alca", rank_qid="Qr2", parent_qid="Q2"))
    # rankless clade in the middle of the chain
    wikidata.add("Q2", make_entity("Pan-Alcidae", parent_qid="Q3"))
    # a second genus-ranked ancestor must not overwrite the first
    wikidata.add("Q3", make_entity("Other", rank_qid="Qr2"))

    rows = run_generator(walk_taxon_chain(db, None, "Q1"))

    assert rows == [("genus", "Q1", "Alca")]
    db.close()


def test_chain_table_round_trip() -> None:
    """Proves chain rows store per (binomial, rank) and read back in full."""
    with SqliteDatabase(":memory:") as db:
        chains = db.taxon_chains_table()
        chains.add("Alca torda", ("species", "Q1", "Alca torda"))
        chains.add("Alca torda", ("family", "Q3", "Alcidae"))

        assert chains.list_binomials() == {"Alca torda"}
        assert list(chains.list_chain("Alca torda")) == [
            ("family", "Q3", "Alcidae"),
            ("species", "Q1", "Alca torda"),
        ]


def make_subject_db() -> SqliteDatabase:
    """Build a database with one photographed razorbill subject."""
    db = SqliteDatabase(":memory:")
    db.photo_metadata_table()
    db.phashes_table()
    db.photos_table()
    fpath = "/album/Published/a.jpg"
    db.conn.execute("insert into photos values (?, '/album/Published')", (fpath,))
    db.conn.execute("insert into phashes values (?, 'h1')", (fpath,))
    db.conn.execute(
        "insert into photo_metadata_table (phash, src_type, relation, target)"
        " values ('h1', 'photo', 'subject', 'urn:ró:bird:alca-torda')"
    )
    db.conn.commit()
    return db


def test_failed_lookups_stay_pending() -> None:
    """Proves binomials whose lookup failed are retried by later scans."""
    with make_subject_db() as db:
        binomials = db.binomials_wikidata_id_table()
        assert list(list_unsaved_binomials(db)) == ["Alca torda"]

        binomials.add("Alca torda", None)
        assert list(list_unsaved_binomials(db)) == ["Alca torda"]

        binomials.add("Alca torda", "Q1")
        assert list(list_unsaved_binomials(db)) == []


def test_non_item_qids_stay_pending() -> None:
    """Proves corrupt non-Q identifiers (e.g. lexeme senses) are re-looked-up."""
    with make_subject_db() as db:
        db.binomials_wikidata_id_table().add("Alca torda", "L1369336-S1")

        assert list(list_unsaved_binomials(db)) == ["Alca torda"]


def test_unknown_slugs_are_not_binomials() -> None:
    """Proves the deliberate 'unknown' subject slug never reaches Wikidata lookup."""
    with make_subject_db() as db:
        db.conn.execute(
            "insert into photo_metadata_table (phash, src_type, relation, target)"
            " values ('h1', 'photo', 'subject', 'urn:ró:bird:unknown?context=wild')"
        )
        db.conn.commit()

        assert list(list_unsaved_binomials(db)) == ["Alca torda"]


def test_taxon_relations_reader() -> None:
    """Proves taxa publish Latin-slugged URNs, Latin names, and English common names."""
    family_entity = {
        "labels": {},
        "claims": {
            "P1843": [{"mainsnak": {"datavalue": {"value": {"text": "auks", "language": "en"}}}}]
        },
    }
    # the order chain label is vernacular; P225 recovers the Latin name
    order_entity = {
        "labels": {"en": {"value": "shorebirds"}},
        "claims": {"P225": [{"mainsnak": {"datavalue": {"value": "Charadriiformes"}}}]},
    }
    # Fakeidae: fictional, so the curated things.toml names cannot couple to this test
    chain_rows = [
        ("Alca torda", ("species", "Q1", "razorbill")),
        ("Alca torda", ("genus", "Q2", "Alca")),
        ("Alca torda", ("family", "Q3", "Fakeidae")),
        ("Alca torda", ("order", "Q4", "shorebirds")),
        ("Alca torda", ("class", "Q5", "bird")),
        ("Unphotographed species", ("family", "Q6", "Ghostidae")),
    ]
    with make_subject_db() as db:
        chains = db.taxon_chains_table()
        for binomial, rank_row in chain_rows:
            chains.add(binomial, rank_row)
        db.wikidata_table().add("Q3", family_entity)
        db.wikidata_table().add("Q4", order_entity)

        triples = [
            (triple.source, triple.relation, triple.target)
            for triple in TaxonRelationsReader.read(db)
        ]

    assert triples == [
        ("urn:ró:bird:alca-torda", "family", "urn:ró:family:fakeidae"),
        ("urn:ró:family:fakeidae", "name", "Fakeidae"),
        ("urn:ró:family:fakeidae", "common_name", "auks"),
        ("urn:ró:bird:alca-torda", "genus", "urn:ró:genus:alca"),
        ("urn:ró:genus:alca", "name", "Alca"),
        ("urn:ró:bird:alca-torda", "order", "urn:ró:order:charadriiformes"),
        ("urn:ró:order:charadriiformes", "name", "Charadriiformes"),
    ]


def test_curated_common_names_win() -> None:
    """Proves a curated things.toml common name beats Wikidata's P1843."""
    with make_subject_db() as db:
        db.wikidata_table().add(
            "Q3",
            {
                "labels": {},
                "claims": {
                    "P1843": [
                        {"mainsnak": {"datavalue": {"value": {"text": "auks", "language": "en"}}}}
                    ]
                },
            },
        )
        curated = {"urn:ró:family:fakeidae": "Curated Auks"}
        scan = ("urn:ró:family:fakeidae", "Q3", "Fakeidae")

        triples = [(t.relation, t.target) for t in taxon_name_triples(db, scan, curated)]
        assert triples == [("name", "Fakeidae"), ("common_name", "Curated Auks")]

        uncurated = [(t.relation, t.target) for t in taxon_name_triples(db, scan, {})]
        assert uncurated == [("name", "Fakeidae"), ("common_name", "auks")]


def test_taxon_listing_entities() -> None:
    """Proves family/genus/order listing entities publish once chains exist."""
    with make_subject_db() as db:
        assert not {"family", "genus", "order"} & listed_types(db)

        db.taxon_chains_table().add("Alca torda", ("family", "Q3", "Alcidae"))
        assert {"family", "genus", "order"} <= listed_types(db)

    triples = [
        (triple.source, triple.relation, triple.target)
        for triple in listing_entity_triples({"family"})
    ]
    assert triples == [
        ("urn:ró:listing:family", "name", "Families"),
        ("urn:ró:listing:family", "listable", "false"),
        ("urn:ró:listing:family", "browseable", "true"),
    ]


def test_list_unchained_binomials() -> None:
    """Proves only QID-bearing binomials without a stored chain are pending."""
    with SqliteDatabase(":memory:") as db:
        binomials = db.binomials_wikidata_id_table()
        binomials.add("Alca torda", "Q1")
        binomials.add("Fratercula arctica", "Q2")
        binomials.add("Mystery species", None)
        db.taxon_chains_table().add("Alca torda", ("species", "Q1", "Alca torda"))

        assert list_unchained_binomials(db) == [("Fratercula arctica", "Q2")]
