"""Publish workflow: build artifacts from the database (env, atom, stats, triples)."""

from __future__ import annotations

import os
from typing import Generator

from zahir import Await, Context, spec, WorkflowOutputEvent

from mirror.commons.config import DATABASE_PATH
from mirror.services.d1 import D1Builder
from mirror.workflows.publish.types import PublishArtifactBundleInput, PublishArtifactsInput
from mirror.workflows.scan.utils import DEFAULT_ALBUMS_MARKDOWN_PATH, DEFAULT_PHOTOS_MARKDOWN_PATH
from mirror.services.database import SqliteDatabase
from mirror.services.metadata import MarkdownAlbumMetadataWriter, MarkdownTablePhotoMetadataWriter
from mirror.workflows.publish.utils import (
    atom_feed,
    atom_media,
    env_content,
    publication_id,
    remove_artifacts,
    stats_content,
    triples_content,
)


@spec()
def PublishEnv(
    context: Context,
    input: PublishArtifactBundleInput,
    dependencies: dict,
) -> Generator[WorkflowOutputEvent]:
    output_dir = input["output_dir"]
    pid = input["publication_id"]
    path = os.path.join(output_dir, "env.json")

    with open(path, "w") as f:
        f.write(env_content(pid))
    yield WorkflowOutputEvent({"artifact": "env"})


@spec()
def PublishAtom(
    context: Context,
    input: PublishArtifactBundleInput,
    dependencies: dict,
) -> Generator[WorkflowOutputEvent]:
    output_dir = input["output_dir"]
    db = SqliteDatabase(DATABASE_PATH)
    atom_feed(atom_media(db), output_dir)

    yield WorkflowOutputEvent({"artifact": "atom"})


@spec()
def PublishStats(
    context: Context,
    input: PublishArtifactBundleInput,
    dependencies: dict,
) -> Generator[WorkflowOutputEvent]:
    output_dir = input["output_dir"]
    pid = input["publication_id"]
    db = SqliteDatabase(DATABASE_PATH)
    path = os.path.join(output_dir, f"stats.{pid}.json")

    with open(path, "w") as f:
        f.write(stats_content(db))

    yield WorkflowOutputEvent({"artifact": "stats"})


@spec()
def PublishTriples(
    context: Context,
    input: PublishArtifactBundleInput,
    dependencies: dict,
) -> Generator[WorkflowOutputEvent]:
    output_dir = input["output_dir"]
    pid = input["publication_id"]
    db = SqliteDatabase(DATABASE_PATH)
    path = os.path.join(output_dir, f"triples.{pid}.json")

    with open(path, "w") as f:
        f.write(triples_content(db))

    yield WorkflowOutputEvent({"artifact": "triples"})


@spec()
def UpdateAlbumsMarkdown(
    context: Context,
    input: PublishArtifactBundleInput,
    dependencies: dict,
) -> Generator[WorkflowOutputEvent]:
    markdown_path = input["albums_markdown_path"]
    db = SqliteDatabase(DATABASE_PATH)
    MarkdownAlbumMetadataWriter().write_album_metadata(db, output_path=markdown_path)
    yield WorkflowOutputEvent({"artifact": "albums_md", "path": markdown_path})


@spec()
def UpdatePhotosMarkdown(
    context: Context,
    input: PublishArtifactBundleInput,
    dependencies: dict,
) -> Generator[WorkflowOutputEvent]:
    markdown_path = input["photos_markdown_path"]
    db = SqliteDatabase(DATABASE_PATH)
    MarkdownTablePhotoMetadataWriter().write_photo_metadata(db, output_path=markdown_path)
    yield WorkflowOutputEvent({"artifact": "photos_md", "path": markdown_path})


@spec()
def PublishD1(
    context: Context,
    input: PublishArtifactBundleInput,
    dependencies: dict,
) -> Generator[WorkflowOutputEvent]:
    db = SqliteDatabase(DATABASE_PATH)
    D1Builder(db).build()
    yield WorkflowOutputEvent({"artifact": "d1"})


@spec()
def PublishArtifacts(
    context: Context,
    input: PublishArtifactsInput,
    dependencies: dict,
) -> Generator[Await | WorkflowOutputEvent]:
    output_dir = input["output_dir"]

    SqliteDatabase(DATABASE_PATH).refresh_dependent_views()

    pid = publication_id()
    remove_artifacts(output_dir)
    builder_inputs: PublishArtifactBundleInput = {
        "output_dir": output_dir,
        "publication_id": pid,
        "albums_markdown_path": input.get("albums_markdown_path", DEFAULT_ALBUMS_MARKDOWN_PATH),
        "photos_markdown_path": input.get("photos_markdown_path", DEFAULT_PHOTOS_MARKDOWN_PATH),
    }

    yield Await(
        [
            PublishEnv(builder_inputs),
            # PublishAtom(builder_inputs),
            PublishStats(builder_inputs),
            PublishTriples(builder_inputs),
            PublishD1(builder_inputs),
        ]
    )

    yield WorkflowOutputEvent({"publication_id": pid})
