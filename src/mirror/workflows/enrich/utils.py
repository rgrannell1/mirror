from pathlib import Path
from typing import Iterator

import tomllib


def read_things(fpath: str) -> Iterator:
    """Read things.toml and yield semantic triples"""

    path = Path(fpath)
    if not path.exists():
        raise ValueError(f"{fpath} does not exist")

    with open(path, "rb") as f:
        data = tomllib.load(f)

    # config keys (binomial_types) and id-less sections (banners) hold no things
    for block in data.values():
        yield from (item for item in block if isinstance(item, dict) and "id" in item)
