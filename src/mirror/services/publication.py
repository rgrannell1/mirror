"""Build publication files and metadata from the media database."""

import os

from mirror.commons.config import DATABASE_PATH
from mirror.services.artifacts import (
    env_content,
    publication_id,
    remove_artifacts,
    stats_content,
    triples_content,
    write_artifact,
)
from mirror.services.atom_publish import atom_feed, atom_media
from mirror.services.d1 import D1Builder
from mirror.services.database import SqliteDatabase
from mirror.services.metadata import (
    MarkdownAlbumMetadataWriter,
    MarkdownTablePhotoMetadataWriter,
    MarkdownTableVideoMetadataWriter,
)


def publish_env(output_dir: str, current_publication_id: str) -> None:
    """Write the environment artifact."""
    path = os.path.join(output_dir, "env.json")
    write_artifact(path, env_content(current_publication_id))


def publish_atom(output_dir: str) -> None:
    """Write the Atom feed artifacts."""
    with SqliteDatabase(DATABASE_PATH) as db:
        media = atom_media(db)
    atom_feed(media, output_dir)


def publish_stats(output_dir: str, current_publication_id: str) -> None:
    """Write the statistics artifact."""
    path = os.path.join(output_dir, f"stats.{current_publication_id}.json")
    with SqliteDatabase(DATABASE_PATH) as db:
        content = stats_content(db)
    write_artifact(path, content)


def publish_triples(output_dir: str, current_publication_id: str) -> None:
    """Write the semantic triples artifact."""
    path = os.path.join(output_dir, f"triples.{current_publication_id}.json")
    with SqliteDatabase(DATABASE_PATH) as db:
        content = triples_content(db)
    write_artifact(path, content)


def write_album_metadata(path: str) -> None:
    """Write album metadata to Markdown."""
    with SqliteDatabase(DATABASE_PATH) as db:
        MarkdownAlbumMetadataWriter().write_album_metadata(db, output_path=path)


def write_photo_metadata(path: str) -> None:
    """Write photo metadata to Markdown."""
    with SqliteDatabase(DATABASE_PATH) as db:
        MarkdownTablePhotoMetadataWriter().write_photo_metadata(db, output_path=path)


def write_video_metadata(path: str) -> None:
    """Write video metadata to Markdown."""
    with SqliteDatabase(DATABASE_PATH) as db:
        MarkdownTableVideoMetadataWriter().write_video_metadata(db, output_path=path)


def build_d1() -> dict:
    """Build the D1 database artifact."""
    with SqliteDatabase(DATABASE_PATH) as db:
        return D1Builder(db).build()


def refresh_database_views() -> None:
    """Refresh all database views used by publication."""
    with SqliteDatabase(DATABASE_PATH) as db:
        db.refresh_dependent_views()


def prepare_artifacts(output_dir: str) -> str:
    """Refresh database views, remove old artifacts, and return a publication ID."""
    refresh_database_views()
    remove_artifacts(output_dir)
    return publication_id()
