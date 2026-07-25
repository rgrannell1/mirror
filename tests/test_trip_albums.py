"""Tests for the audit rule catching albums shot mid-trip but left out of the trip."""

from mirror.audit.checks import find_albums_omitted_from_trips
from mirror.models.album import AlbumDataModel


def make_album(album_id: str, min_date: str, max_date: str) -> AlbumDataModel:
    """Build an album carrying only the id and dates the rule reads."""
    return AlbumDataModel(
        id=album_id,
        name=album_id,
        dpath=f"/media/{album_id}",
        photos_count=1,
        videos_count=0,
        min_date=min_date,
        max_date=max_date,
        thumbnail_url="",
        thumbnail_mosaic_url="",
        mosaic_colours="",
        flags=[],
        description="",
    )


TRIP = "urn:ró:trip:0"
TRIP_ALBUMS = ("urn:ró:album:lisbon-25", "urn:ró:album:madrid-25")

CASES = [
    (
        "album inside the trip range is reported",
        [
            make_album("lisbon-25", "2025:05:01 09:00:00", "2025:05:03 18:00:00"),
            make_album("madrid-25", "2025:05:07 09:00:00", "2025:05:09 18:00:00"),
            make_album("segovia-25", "2025:05:05 09:00:00", "2025:05:05 18:00:00"),
        ],
        ["urn:ró:album:segovia-25"],
    ),
    (
        "albums outside the trip range are ignored",
        [
            make_album("lisbon-25", "2025:05:01 09:00:00", "2025:05:03 18:00:00"),
            make_album("madrid-25", "2025:05:07 09:00:00", "2025:05:09 18:00:00"),
            make_album("dublin-25", "2025:06:01 09:00:00", "2025:06:02 18:00:00"),
        ],
        [],
    ),
    (
        "albums straddling the trip edge are ignored",
        [
            make_album("lisbon-25", "2025:05:01 09:00:00", "2025:05:03 18:00:00"),
            make_album("madrid-25", "2025:05:07 09:00:00", "2025:05:09 18:00:00"),
            make_album("dublin-25", "2025:05:08 09:00:00", "2025:05:20 18:00:00"),
        ],
        [],
    ),
    (
        "undated albums are ignored",
        [
            make_album("lisbon-25", "2025:05:01 09:00:00", "2025:05:03 18:00:00"),
            make_album("madrid-25", "2025:05:07 09:00:00", "2025:05:09 18:00:00"),
            make_album("segovia-25", None, None),
        ],
        [],
    ),
    (
        "a trip whose albums have no dates reports nothing",
        [
            make_album("lisbon-25", None, None),
            make_album("madrid-25", None, None),
            make_album("segovia-25", "2025:05:05 09:00:00", "2025:05:05 18:00:00"),
        ],
        [],
    ),
]


def test_finds_albums_omitted_from_trips() -> None:
    """Proves an album wholly within a trip's dates must be listed in that trip."""
    for description, albums, expected in CASES:
        findings = find_albums_omitted_from_trips({TRIP: TRIP_ALBUMS}, albums)
        assert [finding.subject for finding in findings] == expected, description
