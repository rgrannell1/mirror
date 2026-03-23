from pathlib import Path
import tomllib
from typing import Iterator


def read_things(fpath: str) -> Iterator:
    """Read things.toml and yield semantic triples"""

    path = Path(fpath)
    if not path.exists():
        raise ValueError(f"{fpath} does not exist")

    with open(path, "rb") as f:
        data = tomllib.load(f)

    for block in data.values():
        for item in block:
            yield item
