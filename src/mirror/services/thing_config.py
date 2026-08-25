"""Read configured things from TOML."""

from collections.abc import Iterator
from pathlib import Path

import tomllib


def read_things(fpath: str) -> Iterator[dict[str, object]]:
    """Yield configured things with IDs."""
    path = Path(fpath)
    if not path.exists():
        raise ValueError(f"{fpath} does not exist")

    with path.open("rb") as file_handle:
        data = tomllib.load(file_handle)

    for block in data.values():
        yield from (item for item in block if isinstance(item, dict) and "id" in item)
