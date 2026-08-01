"""Tests for the trip social-card image choice."""

from mirror.services.d1 import choose_trip_image, collect_album_covers

ALBUM_URNS = (
    "urn:ró:album:toledo-26",
    "urn:ró:album:madrid-city-26",
    "urn:ró:album:man-26",
)

PERMALINK_TO_DPATH = {
    "toledo-26": "/media/toledo",
    "madrid-city-26": "/media/madrid",
    "man-26": "/media/man",
}

DETAILS = {
    "/media/toledo": {"image_url": "https://cdn/toledo.webp"},
    "/media/madrid": {"image_url": "https://cdn/madrid.webp"},
    "/media/man": {"image_url": "https://cdn/man.webp"},
}

CASES = [
    (
        "highest-rated cover wins",
        {"/media/toledo": 2, "/media/madrid": 4, "/media/man": 3},
        {"/media/toledo": "2026:02:20", "/media/madrid": "2026:02:22", "/media/man": "2026:02:28"},
        "https://cdn/madrid.webp",
    ),
    (
        "rating tie favours the newest album",
        {"/media/toledo": 3, "/media/madrid": 3, "/media/man": 3},
        {"/media/toledo": "2026:02:20", "/media/madrid": "2026:02:22", "/media/man": "2026:02:28"},
        "https://cdn/man.webp",
    ),
    (
        "unrated covers rank below rated covers",
        {"/media/man": 1},
        {"/media/toledo": "2026:02:20", "/media/madrid": "2026:02:22", "/media/man": "2026:02:18"},
        "https://cdn/man.webp",
    ),
]


def test_choose_trip_image() -> None:
    """Proves the trip card picks the best-rated, then newest, album cover."""
    for label, ratings, max_dates, expected in CASES:
        album_covers = collect_album_covers(DETAILS, ratings, max_dates)
        chosen = choose_trip_image(ALBUM_URNS, PERMALINK_TO_DPATH, album_covers)
        assert chosen == expected, label


def test_choose_trip_image_without_covers() -> None:
    """Proves a trip with no album cover images yields no card image."""
    chosen = choose_trip_image(ALBUM_URNS, PERMALINK_TO_DPATH, {})
    assert chosen is None
