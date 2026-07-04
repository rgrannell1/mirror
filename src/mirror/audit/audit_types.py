"""Types for the publication-readiness audit: findings and the checks that emit them."""

from collections.abc import Callable, Iterator
from dataclasses import dataclass

from mirror.services.database import SqliteDatabase


@dataclass(frozen=True)
class Finding:
    """A single publication-blocking issue against one album or photo."""

    check: str
    subject: str
    detail: str


type CheckFn = Callable[[SqliteDatabase], Iterator[Finding]]


@dataclass(frozen=True)
class Check:
    """A named audit rule: a human description plus the function that runs it."""

    slug: str
    description: str
    run: CheckFn
