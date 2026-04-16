"""Recreate SQLite views with cross-dependencies (must run from a single writer)."""

from __future__ import annotations

import sqlite3

from mirror.commons.tables import (
    ALBUM_CONTENTS_VIEW,
    ALBUM_DATA_VIEW,
    PHOTO_DATA_VIEW,
    PHOTO_METADATA_SUMMARY,
    PHOTO_METADATA_VIEW,
    VIDEO_DATA_VIEW,
    VIDEO_METADATA_SUMMARY,
    VIDEO_METADATA_VIEW,
)


def refresh_dependent_views(conn: sqlite3.Connection) -> None:
    """Drop and recreate album-backed views in dependency order.

    Parallel connections must not run DDL on these views; call this once before
    concurrent readers (e.g. start of publish) or at scan entry.
    """
    conn.execute("DROP VIEW IF EXISTS view_photo_metadata_summary")
    conn.execute("DROP VIEW IF EXISTS view_photo_metadata")
    conn.execute("DROP VIEW IF EXISTS view_video_metadata_summary")
    conn.execute("DROP VIEW IF EXISTS view_video_metadata")
    conn.execute("DROP VIEW IF EXISTS view_photo_data")
    conn.execute("DROP VIEW IF EXISTS view_video_data")
    conn.execute("DROP VIEW IF EXISTS view_album_data")
    conn.execute("DROP VIEW IF EXISTS view_album_contents")
    conn.execute(ALBUM_CONTENTS_VIEW)
    conn.execute(ALBUM_DATA_VIEW)
    conn.execute(PHOTO_DATA_VIEW)
    conn.execute(VIDEO_DATA_VIEW)
    conn.execute(PHOTO_METADATA_VIEW)
    conn.execute(PHOTO_METADATA_SUMMARY)
    conn.execute(VIDEO_METADATA_VIEW)
    conn.execute(VIDEO_METADATA_SUMMARY)
    conn.commit()
