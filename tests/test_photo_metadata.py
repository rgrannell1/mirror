"""Tests for photo metadata database access."""

import sqlite3

from mirror.services.database.photos import PhotoMetadataTable


def test_photo_metadata_list_ignores_rows_for_removed_photos() -> None:
    """Proves stale phash metadata cannot create orphan published photo triples."""
    conn = sqlite3.connect(":memory:")
    conn.execute("create table phashes (fpath text, phash text primary key)")
    conn.execute("create table photos (fpath text primary key)")
    metadata = PhotoMetadataTable(conn)
    fpath = "/media/2020/album/Published/removed.jpg"
    conn.execute("insert into phashes values (?, ?)", (fpath, "hash"))
    conn.execute("insert into photo_metadata_table values ('hash', 'photo', 'rating', '⭐')")

    assert list(metadata.list()) == []
