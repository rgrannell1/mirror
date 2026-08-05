"""Tests for domain properties loaded from things.toml."""

from pathlib import Path

from mirror.data.things import (
    animal_contexts,
    animal_types,
    binomial_types,
    feature_urn_for_role,
    genre_cover_priorities,
    rating_ids,
    rating_names,
    rating_ranks,
    rating_urns_by_name,
    unlisted_types,
)

DOMAIN_DATA = """
subject_types = [
    { noun = "newt", animal = true, binomial = true, context = "wild" },
    { noun = "person", listed = false },
]
genres = [
    { id = "panorama", cover_priority = { album = 2, place = 0 } },
]
place_features = [
    { id = "urn:ró:place_feature:nation", roles = ["country"] },
]
ratings = [
    { id = "urn:ró:rating:low", name = "Low", rank = 1 },
    { id = "urn:ró:rating:high", name = "High", rank = 2 },
]
"""


def write_domain_data(tmp_path: Path) -> str:
    """Write isolated domain data and return its path."""
    things_path = tmp_path / "things.toml"
    things_path.write_text(DOMAIN_DATA)
    return str(things_path)


def test_subject_properties_come_from_things(tmp_path: Path) -> None:
    """Proves subject behaviour comes from configured properties."""
    things_path = write_domain_data(tmp_path)

    assert animal_types(things_path) == ("newt",)
    assert animal_contexts(things_path) == {"newt": "wild"}
    assert binomial_types(things_path) == {"newt"}
    assert unlisted_types(things_path) == {"person"}


def test_rating_properties_come_from_things(tmp_path: Path) -> None:
    """Proves rating identity, display order, and rank come from configured properties."""
    things_path = write_domain_data(tmp_path)

    assert rating_ids(things_path) == ("urn:ró:rating:low", "urn:ró:rating:high")
    assert rating_names(things_path) == ("Low", "High")
    assert rating_urns_by_name(things_path) == {
        "Low": "urn:ró:rating:low",
        "High": "urn:ró:rating:high",
    }
    assert rating_ranks(things_path) == {"Low": 1, "High": 2}


def test_feature_and_genre_properties_come_from_things(tmp_path: Path) -> None:
    """Proves feature roles and cover priorities come from configured properties."""
    things_path = write_domain_data(tmp_path)

    assert feature_urn_for_role("country", things_path) == "urn:ró:place_feature:nation"
    assert genre_cover_priorities("album", things_path) == {"panorama": 2}
    assert genre_cover_priorities("place", things_path) == {"panorama": 0}
