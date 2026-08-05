"""Tests for the listing entity reader."""

from mirror.data.semantic_triples.listings import listing_entity_triples


def test_listing_entities_derive_from_sections() -> None:
    """Proves listed types gain a name from their section header, binomial types are
    flagged, and excluded or sectionless types emit nothing."""
    triples = list(listing_entity_triples({"bird", "cnidaria", "person", "notatype"}))

    as_tuples = [(triple.source, triple.relation, triple.target) for triple in triples]
    assert as_tuples == [
        ("urn:ró:listing:bird", "name", "Birds"),
        ("urn:ró:listing:bird", "binomial", "true"),
        ("urn:ró:listing:cnidaria", "name", "Cnidaria"),
    ]
