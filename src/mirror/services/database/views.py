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

# Views dropped in reverse dependency order before recreation
DROPPED_VIEWS = (
    "view_photo_metadata_summary",
    "view_photo_metadata",
    "view_video_metadata_summary",
    "view_video_metadata",
    "view_photo_data",
    "view_video_data",
    "view_album_data",
    "view_album_contents",
)

# View DDL statements, in dependency order
CREATED_VIEWS = (
    ALBUM_CONTENTS_VIEW,
    ALBUM_DATA_VIEW,
    PHOTO_DATA_VIEW,
    VIDEO_DATA_VIEW,
    PHOTO_METADATA_VIEW,
    PHOTO_METADATA_SUMMARY,
    VIDEO_METADATA_VIEW,
    VIDEO_METADATA_SUMMARY,
)


def refresh_dependent_views(conn: sqlite3.Connection) -> None:
    """Drop and recreate album-backed views in dependency order.

    Parallel connections must not run DDL on these views; call this once before
    concurrent readers (e.g. start of publish) or at scan entry.
    """
    for view_name in DROPPED_VIEWS:
        conn.execute(f"DROP VIEW IF EXISTS {view_name}")

    for view_ddl in CREATED_VIEWS:
        conn.execute(view_ddl)

    conn.commit()
