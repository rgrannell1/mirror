"""Shared test fixtures: minimal in-memory media databases."""

from mirror.services.database import SqliteDatabase


def make_media_db() -> SqliteDatabase:
    """Build an empty in-memory media database with all tables and views."""
    db = SqliteDatabase(":memory:")
    for accessor in (
        db.photos_table,
        db.phashes_table,
        db.photo_metadata_table,
        db.exif_table,
        db.subject_detections_table,
        db.videos_table,
        db.encoded_photos_table,
        db.encoded_videos_table,
        db.taxon_chains_table,
        db.wikidata_table,
        db.binomials_wikidata_id_table,
    ):
        accessor()

    # scan owns this table's creation; tests recreate the shape by hand
    db.conn.execute(
        "create table media_metadata_table (src text, src_type text, relation text, target text)"
    )
    db.refresh_dependent_views()
    return db


def add_published_photo(db: SqliteDatabase, fpath: str, phash: str, subject_urn: str) -> None:
    """Insert one published photo with a subject, thumbnail, and album permalink."""
    dpath = fpath.rsplit("/", 1)[0]
    db.conn.execute("insert or ignore into photos values (?, ?)", (fpath, dpath))
    db.conn.execute("insert or ignore into phashes values (?, ?)", (fpath, phash))
    db.conn.execute(
        "insert into photo_metadata_table (phash, src_type, relation, target)"
        " values (?, 'photo', 'subject', ?)",
        (phash, subject_urn),
    )
    db.conn.execute(
        "insert or ignore into encoded_photos (fpath, mimetype, role, url)"
        " values (?, 'image/webp', 'thumbnail_lossy', 'https://cdn/' || ? || '.webp')",
        (fpath, phash),
    )
    db.conn.execute(
        "insert or ignore into media_metadata_table values (?, 'album', 'permalink', 'album-26')",
        (dpath,),
    )
    db.conn.commit()
