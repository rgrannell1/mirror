"""Enrich configured things through Zahir jobs."""

from collections.abc import Generator, Iterator
from typing import TypedDict, cast

from zahir import JobContext, await_all

from mirror.services.thing_config import read_things


class PlaceInput(TypedDict):
    """Input for one place enrichment job."""

    place: dict[str, object]


class EnrichInput(TypedDict):
    """Input for the root enrichment job."""


def filter_things(
    subject_type: str, things: list[dict[str, object]]
) -> Iterator[dict[str, object]]:
    """Yield configured things of one URN type."""
    for thing in things:
        thing_id = thing.get("id")
        if isinstance(thing_id, str) and thing_id.startswith(f"urn:ró:{subject_type}:"):
            yield thing


def enrich_place(ctx: JobContext, input: PlaceInput) -> Generator[object, object, PlaceInput]:
    """Return one place after its enrichment step."""
    return input
    yield


def enrich_data(ctx: JobContext, input: EnrichInput) -> Generator[object, object, list[PlaceInput]]:
    """Enrich all configured places in parallel."""
    things = list(read_things("things.toml"))
    jobs = [ctx.scope.enrich_place({"place": thing}) for thing in filter_things("place", things)]
    results = yield await_all(jobs)
    return cast(list[PlaceInput], results)
    yield
