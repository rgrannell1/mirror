"""Tests for hidden Miscellaneous albums: their photos publish, the album itself does not."""

import sqlite3

from mirror.commons.constants import MISCELLANEOUS_ALBUM_ID
from mirror.commons.utils import is_miscellaneous_dpath
from mirror.data.semantic_triples.albums import AlbumTriples
from mirror.models.album import AlbumDataModel
from mirror.workflows.scan.utils import write_miscellaneous_permalinks

DPATH_CASES = [
    ("/media/2026/Miscellaneous/Published", True),
    ("/media/2025/Miscellaneous/Published", True),
    ("/media/2026/Miscellaneous", True),
    ("/media/2026/Maynooth/Published", False),
    ("/media/2026/Maynooth", False),
    ("/media/2026/miscellaneous/Published", False),
]


def test_is_miscellaneous_dpath() -> None:
    """Proves Miscellaneous album folders and their Published subfolders count as hidden."""
    for dpath, expected in DPATH_CASES:
        assert is_miscellaneous_dpath(dpath) == expected, dpath


class StubMetadataDatabase:
    """Bare media tables; write_miscellaneous_permalinks only touches db.conn."""

    def __init__(self, photo_dpaths: list[str], video_dpaths: list[str]) -> None:
        self.conn = sqlite3.connect(":memory:")
        self.conn.execute("create table photos (dpath text)")
        self.conn.execute("create table videos (dpath text)")
        metadata_schema = "src text, src_type text, relation text, target text"
        self.conn.execute(f"create table media_metadata_table ({metadata_schema})")
        for dpath in photo_dpaths:
            self.conn.execute("insert into photos values (?)", (dpath,))
        for dpath in video_dpaths:
            self.conn.execute("insert into videos values (?)", (dpath,))


def test_write_miscellaneous_permalinks() -> None:
    """Proves every Miscellaneous dpath gains the shared hidden permalink; others gain none."""
    database = StubMetadataDatabase(
        photo_dpaths=[
            "/media/2026/Miscellaneous/Published",
            "/media/2026/Maynooth/Published",
        ],
        video_dpaths=["/media/2025/Miscellaneous/Published"],
    )

    write_miscellaneous_permalinks(database)

    rows = database.conn.execute(
        "select src, src_type, relation, target from media_metadata_table order by src"
    ).fetchall()
    assert rows == [
        ("/media/2025/Miscellaneous/Published", "album", "permalink", MISCELLANEOUS_ALBUM_ID),
        ("/media/2026/Miscellaneous/Published", "album", "permalink", MISCELLANEOUS_ALBUM_ID),
    ]


def make_album(album_id: str, dpath: str) -> AlbumDataModel:
    """Build a dated album carrying the fields AlbumTriples reads."""
    return AlbumDataModel(
        id=album_id,
        name=album_id,
        dpath=dpath,
        photos_count=1,
        videos_count=0,
        min_date="2026:01:01 09:00:00",
        max_date="2026:01:02 18:00:00",
        thumbnail_url="",
        thumbnail_mosaic_url="",
        mosaic_colours="",
        flags=[],
        description="",
    )


class StubAlbumDataView:
    def __init__(self, albums: list[AlbumDataModel]) -> None:
        self.albums = albums

    def list(self) -> list[AlbumDataModel]:
        return self.albums


class StubTriplesDatabase:
    def __init__(self, albums: list[AlbumDataModel]) -> None:
        self.view = StubAlbumDataView(albums)

    def album_data_view(self) -> StubAlbumDataView:
        return self.view


def test_album_triples_skips_miscellaneous() -> None:
    """Proves no album triples are published for the hidden miscellaneous album."""
    database = StubTriplesDatabase([
        make_album(MISCELLANEOUS_ALBUM_ID, "/media/2026/Miscellaneous/Published"),
        make_album("maynooth-26", "/media/2026/Maynooth/Published"),
    ])

    triples = list(AlbumTriples().read(database))

    sources = {triple.source for triple in triples}
    assert f"urn:ró:album:{MISCELLANEOUS_ALBUM_ID}" not in sources
    assert "urn:ró:album:maynooth-26" in sources
