"""Publish workflow: build artifacts from the database (env, atom, stats, triples)."""

from __future__ import annotations

import os
from collections.abc import Generator
from typing import Any

from zahir import EAwait, JobContext

from mirror.commons.config import DATABASE_PATH
from mirror.services.d1 import D1Builder
from mirror.workflows.publish.types import PublishArtifactBundleInput, PublishArtifactsInput
from mirror.workflows.scan.utils import (
    DEFAULT_ALBUMS_MARKDOWN_PATH,
    DEFAULT_PHOTOS_MARKDOWN_PATH,
    DEFAULT_VIDEOS_MARKDOWN_PATH,
)
from mirror.services.database import SqliteDatabase
from mirror.services.metadata import (
    MarkdownAlbumMetadataWriter,
    MarkdownTablePhotoMetadataWriter,
    MarkdownTableVideoMetadataWriter,
)
from mirror.workflows.publish.atom import atom_feed, atom_media
from mirror.workflows.publish.utils import (
    env_content,
    publication_id,
    remove_artifacts,
    stats_content,
    triples_content,
)


def publish_env(ctx: JobContext, input: PublishArtifactBundleInput) -> Generator[Any, Any, dict]:
    output_dir = input["output_dir"]
    pid = input["publication_id"]
    path = os.path.join(output_dir, "env.json")

    with open(path, "w") as f:
        f.write(env_content(pid))

    return {"artifact": "env"}
    yield


def publish_atom(ctx: JobContext, input: PublishArtifactBundleInput) -> Generator[Any, Any, dict]:
    output_dir = input["output_dir"]
    db = SqliteDatabase(DATABASE_PATH)
    media = atom_media(db)
    atom_feed(media, output_dir)
    return {"artifact": "atom"}
    yield


def publish_stats(ctx: JobContext, input: PublishArtifactBundleInput) -> Generator[Any, Any, dict]:
    output_dir = input["output_dir"]
    pid = input["publication_id"]
    db = SqliteDatabase(DATABASE_PATH)
    path = os.path.join(output_dir, f"stats.{pid}.json")

    with open(path, "w") as f:
        f.write(stats_content(db))

    return {"artifact": "stats"}
    yield


def publish_triples(ctx: JobContext, input: PublishArtifactBundleInput) -> Generator[Any, Any, dict]:
    output_dir = input["output_dir"]
    pid = input["publication_id"]
    db = SqliteDatabase(DATABASE_PATH)
    path = os.path.join(output_dir, f"triples.{pid}.json")

    with open(path, "w") as f:
        f.write(triples_content(db))

    return {"artifact": "triples"}
    yield


def update_albums_markdown(ctx: JobContext, input: PublishArtifactBundleInput) -> Generator[Any, Any, dict]:
    markdown_path = input["albums_markdown_path"]
    db = SqliteDatabase(DATABASE_PATH)
    MarkdownAlbumMetadataWriter().write_album_metadata(db, output_path=markdown_path)
    return {"artifact": "albums_md", "path": markdown_path}
    yield


def update_photos_markdown(ctx: JobContext, input: PublishArtifactBundleInput) -> Generator[Any, Any, dict]:
    markdown_path = input["photos_markdown_path"]
    db = SqliteDatabase(DATABASE_PATH)
    MarkdownTablePhotoMetadataWriter().write_photo_metadata(db, output_path=markdown_path)
    return {"artifact": "photos_md", "path": markdown_path}
    yield


def update_videos_markdown(ctx: JobContext, input: PublishArtifactBundleInput) -> Generator[Any, Any, dict]:
    markdown_path = input["videos_markdown_path"]
    db = SqliteDatabase(DATABASE_PATH)
    MarkdownTableVideoMetadataWriter().write_video_metadata(db, output_path=markdown_path)
    return {"artifact": "videos_md", "path": markdown_path}
    yield


def publish_d1(ctx: JobContext, input: PublishArtifactBundleInput) -> Generator[Any, Any, dict]:
    db = SqliteDatabase(DATABASE_PATH)
    D1Builder(db).build()
    return {"artifact": "d1"}
    yield


def publish_artifacts(ctx: JobContext, input: PublishArtifactsInput) -> Generator[Any, Any, dict]:
    output_dir = input["output_dir"]

    SqliteDatabase(DATABASE_PATH).refresh_dependent_views()

    pid = publication_id()
    remove_artifacts(output_dir)

    builder_inputs: PublishArtifactBundleInput = {
        "output_dir": output_dir,
        "publication_id": pid,
        "albums_markdown_path": input.get("albums_markdown_path", DEFAULT_ALBUMS_MARKDOWN_PATH),
        "photos_markdown_path": input.get("photos_markdown_path", DEFAULT_PHOTOS_MARKDOWN_PATH),
        "videos_markdown_path": input.get("videos_markdown_path", DEFAULT_VIDEOS_MARKDOWN_PATH),
    }

    yield EAwait(
        [
            ctx.scope.publish_env(builder_inputs),
            ctx.scope.publish_stats(builder_inputs),
            ctx.scope.publish_triples(builder_inputs),
            ctx.scope.publish_d1(builder_inputs),
            ctx.scope.update_albums_markdown(builder_inputs),
            ctx.scope.update_photos_markdown(builder_inputs),
            ctx.scope.update_videos_markdown(builder_inputs),
        ]
    )

    return {"publication_id": pid}
