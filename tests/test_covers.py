"""Tests for the shared, funes-cached cover selection."""

import os
import sqlite3
import tempfile

from conftest import add_published_photo, make_media_db

from mirror.data.covers import (
    cached_cover_selection,
    cover_fpaths,
    cover_inputs_key,
    read_cover_inputs,
    select_covers,
)

RAZORBILL = "urn:ró:bird:alca-torda"
FPATH = "/media/2026/Birds/Published/a.jpg"


def make_covers_db():
    """A database with one published, subject-labelled photo."""
    db = make_media_db()
    add_published_photo(db, FPATH, "h1", RAZORBILL)
    return db


def test_select_covers_picks_subject_photo() -> None:
    """Proves a subject-labelled photo becomes the thing and listing cover."""
    with make_covers_db() as db:
        selection = select_covers(read_cover_inputs(db))

    assert selection.things == {RAZORBILL: FPATH}
    assert selection.listings == {"urn:ró:listing:bird": FPATH}


def test_cached_selection_matches_direct() -> None:
    """Proves the cached selection equals the direct one and reuses its store entry."""
    with make_covers_db() as db, tempfile.TemporaryDirectory() as tmp:
        cache_path = os.path.join(tmp, "cache.db")
        direct = select_covers(read_cover_inputs(db))

        first = cached_cover_selection(db, cache_path)
        second = cached_cover_selection(db, cache_path)

        assert first == second == direct
        with sqlite3.connect(cache_path) as cache:
            assert cache.execute("select count(*) from memo").fetchone()[0] == 1


def test_changed_metadata_busts_cache() -> None:
    """Proves a metadata edit changes the cache key, so the selection recomputes."""
    with make_covers_db() as db, tempfile.TemporaryDirectory() as tmp:
        cache_path = os.path.join(tmp, "cache.db")
        cached_cover_selection(db, cache_path)

        db.conn.execute(
            "insert into photo_metadata_table (phash, src_type, relation, target)"
            " values ('h1', 'photo', 'rating', '⭐⭐⭐')"
        )
        db.conn.commit()
        db.refresh_dependent_views()
        cached_cover_selection(db, cache_path)

        with sqlite3.connect(cache_path) as cache:
            assert cache.execute("select count(*) from memo").fetchone()[0] == 2


def test_input_key_ignores_row_order() -> None:
    """Proves the cache key is stable under input row reordering."""
    with make_covers_db() as db:
        add_published_photo(db, "/media/2026/Birds/Published/b.jpg", "h2", RAZORBILL)
        inputs = read_cover_inputs(db)

    reordered = inputs._replace(thing_rows=tuple(reversed(inputs.thing_rows)))
    assert cover_inputs_key(inputs) == cover_inputs_key(reordered)


def test_input_key_busts_on_param_change() -> None:
    """Proves changed algorithm parameters change the cache key."""
    with make_covers_db() as db:
        inputs = read_cover_inputs(db)

    changed = inputs._replace(params=(*inputs.params, "changed"))
    assert cover_inputs_key(inputs) != cover_inputs_key(changed)


def test_cover_fpaths_gathers_all_sections() -> None:
    """Proves cover_fpaths returns each selected photo exactly once."""
    with make_covers_db() as db, tempfile.TemporaryDirectory() as tmp:
        cache_path = os.path.join(tmp, "cache.db")
        assert cover_fpaths(db, cache_path) == frozenset({FPATH})
