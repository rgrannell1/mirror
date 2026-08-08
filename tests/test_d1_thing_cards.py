"""Tests for thing-page social cards in the D1 build."""

from mirror.data.covers import CoverSelection, thing_card_pairs
from mirror.services.d1 import thing_card_rows, thing_display_name

SELECTION = CoverSelection(
    things={"urn:ró:bird:alca-torda": "/media/a.jpg"},
    taxa={"urn:ró:family:alcidae": "/media/a.jpg"},
    listings={"urn:ró:listing:bird": "/media/a.jpg"},
    features={
        "urn:ró:place_feature:castle": "/media/b.jpg",
        "urn:ró:listing:place_feature": "/media/b.jpg",
    },
)


def test_thing_card_pairs_excludes_listings() -> None:
    """Proves listing covers get no thing card: no thing page exists for them."""
    urns = {urn for urn, _ in thing_card_pairs(SELECTION)}

    assert urns == {
        "urn:ró:bird:alca-torda",
        "urn:ró:family:alcidae",
        "urn:ró:place_feature:castle",
    }


NAME_CASES = [
    ("a curated name wins", "urn:ró:bird:alca-torda", {"urn:ró:bird:alca-torda": "Razorbill"}),
    ("an unnamed thing title-cases its id", "urn:ró:bird:blue-tit", {}),
    ("a taxon title-cases its slug", "urn:ró:family:alcidae", {}),
]

NAME_EXPECTED = ["Razorbill", "Blue Tit", "Alcidae"]


def test_thing_display_name() -> None:
    """Proves curated names win and unnamed things fall back to their title-cased id."""
    for (label, urn, names), expected in zip(NAME_CASES, NAME_EXPECTED):
        assert thing_display_name(urn, names) == expected, label


def test_thing_card_rows_prefers_social_card_encode() -> None:
    """Proves cards use the social_card encode, falling back to the mid-size image."""
    social_urls = {"/media/a.jpg": "https://cdn/a-social.webp"}
    mid_urls = {"/media/b.jpg": "https://cdn/b-mid.webp"}

    cards, fallbacks = thing_card_rows(SELECTION, social_urls, mid_urls, {})

    by_path = {card.path: card.image_url for card in cards}
    assert by_path == {
        "/thing/bird:alca-torda": "https://cdn/a-social.webp",
        "/thing/family:alcidae": "https://cdn/a-social.webp",
        "/thing/place_feature:castle": "https://cdn/b-mid.webp",
    }
    assert fallbacks == ["urn:ró:place_feature:castle"]


def test_thing_card_rows_skips_unencoded_covers() -> None:
    """Proves a thing whose cover has no encode at all gets no card."""
    cards, fallbacks = thing_card_rows(SELECTION, {}, {}, {})

    assert cards == []
    assert set(fallbacks) == set()
