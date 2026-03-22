from typing import Generator, Iterator, TypedDict
from zahir import Await, Context, DependencyGroup, JobOutputEvent, WorkflowOutputEvent, spec

from mirror.workflows.enrich.utils import read_things
from mirror.commons.config import DATABASE_PATH
from mirror.services.database import SqliteDatabase


def filter_things(type: str, things: list[dict]) -> Iterator[dict]:
    for thing in things:
        if thing["id"].startswith(f"urn:ró:{type}:"):
            yield thing


class PlaceType(TypedDict):
    place: dict


@spec(args=PlaceType, output=PlaceType)
def EnrichPlace(
    context: Context,
    input: PlaceType,
    dependencies: DependencyGroup,
) -> Generator[JobOutputEvent]:
    place = input["place"]

    yield JobOutputEvent({"place": place})


@spec()
def EnrichData(
    context: Context,
    input,
    dependencies: DependencyGroup,
) -> Generator[Await | WorkflowOutputEvent]:
    db = SqliteDatabase(DATABASE_PATH)
    things = list(read_things("things.toml"))

    places = yield Await([EnrichPlace({"place": thing}) for thing in filter_things("place", things)])
