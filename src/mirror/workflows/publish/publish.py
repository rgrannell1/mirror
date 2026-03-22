"""Publish workflow: build artifacts from the database (env, atom, stats, triples)."""

from __future__ import annotations

import os
from typing import Generator

from zahir import Await, Context, spec, WorkflowOutputEvent

from mirror.commons.config import DATABASE_PATH
from mirror.services.database import SqliteDatabase
from mirror.commands.publish.utils import (
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
    input: dict,
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
    input: dict,
    dependencies: dict,
) -> Generator[WorkflowOutputEvent]:

    output_dir = input["output_dir"]
    db = SqliteDatabase(DATABASE_PATH)
    atom_feed(atom_media(db), output_dir)

    yield WorkflowOutputEvent({"artifact": "atom"})


@spec()
def PublishStats(
    context: Context,
    input: dict,
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
    input: dict,
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
def PublishArtifacts(
    context: Context,
    input: dict,
    dependencies: dict,
) -> Generator[Await | WorkflowOutputEvent]:
    output_dir = input["output_dir"]

    pid = publication_id()
    remove_artifacts(output_dir)
    builder_inputs = {"output_dir": output_dir, "publication_id": pid}

    yield Await([
      PublishEnv(builder_inputs, {}),
      #PublishAtom(builder_inputs, {}),
      PublishStats(builder_inputs, {}),
      PublishTriples(builder_inputs, {}),
    ])

    yield WorkflowOutputEvent({"publication_id": pid})
