"""Publish workflow: build artifacts from the database (env, atom, stats, triples)."""

from __future__ import annotations

from collections.abc import Generator
from typing import Any

from zahir import JobContext, await_all

from mirror.services.artifacts import publication_id
from mirror.services.media_scan import (
    DEFAULT_ALBUMS_MARKDOWN_PATH,
    DEFAULT_PHOTOS_MARKDOWN_PATH,
    DEFAULT_VIDEOS_MARKDOWN_PATH,
)
from mirror.services.publication import (
    build_d1,
    prepare_artifacts,
    refresh_database_views,
    write_album_metadata,
    write_photo_metadata,
    write_video_metadata,
)
from mirror.services.publication import (
    publish_atom as publish_atom_service,
)
from mirror.services.publication import (
    publish_env as publish_env_service,
)
from mirror.services.publication import (
    publish_stats as publish_stats_service,
)
from mirror.services.publication import (
    publish_triples as publish_triples_service,
)
from mirror.workflows.publish.types import PublishArtifactBundleInput, PublishArtifactsInput


def publish_env(ctx: JobContext, input: PublishArtifactBundleInput) -> Generator[Any, Any, dict]:
    publish_env_service(input["output_dir"], input["publication_id"])

    return {"artifact": "env"}
    yield


def publish_atom(ctx: JobContext, input: PublishArtifactBundleInput) -> Generator[Any, Any, dict]:
    publish_atom_service(input["output_dir"])
    return {"artifact": "atom"}
    yield


def publish_stats(ctx: JobContext, input: PublishArtifactBundleInput) -> Generator[Any, Any, dict]:
    publish_stats_service(input["output_dir"], input["publication_id"])

    return {"artifact": "stats"}
    yield


def publish_triples(
    ctx: JobContext, input: PublishArtifactBundleInput
) -> Generator[Any, Any, dict]:
    publish_triples_service(input["output_dir"], input["publication_id"])

    return {"artifact": "triples"}
    yield


def update_albums_markdown(
    ctx: JobContext, input: PublishArtifactBundleInput
) -> Generator[Any, Any, dict]:
    markdown_path = input["albums_markdown_path"]
    write_album_metadata(markdown_path)
    return {"artifact": "albums_md", "path": markdown_path}
    yield


def update_photos_markdown(
    ctx: JobContext, input: PublishArtifactBundleInput
) -> Generator[Any, Any, dict]:
    markdown_path = input["photos_markdown_path"]
    write_photo_metadata(markdown_path)
    return {"artifact": "photos_md", "path": markdown_path}
    yield


def update_videos_markdown(
    ctx: JobContext, input: PublishArtifactBundleInput
) -> Generator[Any, Any, dict]:
    markdown_path = input["videos_markdown_path"]
    write_video_metadata(markdown_path)
    return {"artifact": "videos_md", "path": markdown_path}
    yield


def publish_d1(ctx: JobContext, input: PublishArtifactBundleInput) -> Generator[Any, Any, dict]:
    summary = build_d1()
    return {"artifact": "d1", **summary}
    yield


def write_metadata(ctx: JobContext, input: PublishArtifactsInput) -> Generator[Any, Any, dict]:
    """Rewrite the human-editable markdown metadata files from the database.

    Runs before the audit gate: newly-indexed photos must surface in photos.md so they become
    labellable. The audit must never block the step that lets you clear the audit's findings.
    """
    refresh_database_views()

    builder_inputs: PublishArtifactBundleInput = {
        "output_dir": input["output_dir"],
        "publication_id": publication_id(),
        "albums_markdown_path": input.get("albums_markdown_path", DEFAULT_ALBUMS_MARKDOWN_PATH),
        "photos_markdown_path": input.get("photos_markdown_path", DEFAULT_PHOTOS_MARKDOWN_PATH),
        "videos_markdown_path": input.get("videos_markdown_path", DEFAULT_VIDEOS_MARKDOWN_PATH),
    }

    yield await_all([
        ctx.scope.update_albums_markdown(builder_inputs),
        ctx.scope.update_photos_markdown(builder_inputs),
        ctx.scope.update_videos_markdown(builder_inputs),
    ])

    return {"complete": True}


def publish_artifacts(ctx: JobContext, input: PublishArtifactsInput) -> Generator[Any, Any, dict]:
    output_dir = input["output_dir"]

    pid = prepare_artifacts(output_dir)

    builder_inputs: PublishArtifactBundleInput = {
        "output_dir": output_dir,
        "publication_id": pid,
        "albums_markdown_path": input.get("albums_markdown_path", DEFAULT_ALBUMS_MARKDOWN_PATH),
        "photos_markdown_path": input.get("photos_markdown_path", DEFAULT_PHOTOS_MARKDOWN_PATH),
        "videos_markdown_path": input.get("videos_markdown_path", DEFAULT_VIDEOS_MARKDOWN_PATH),
    }

    yield await_all([
        ctx.scope.publish_env(builder_inputs),
        ctx.scope.publish_atom(builder_inputs),
        ctx.scope.publish_stats(builder_inputs),
        ctx.scope.publish_triples(builder_inputs),
        ctx.scope.publish_d1(builder_inputs),
    ])

    return {"publication_id": pid}
