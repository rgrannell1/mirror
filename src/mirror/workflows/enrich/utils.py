from pathlib import Path
import tomllib
from typing import Iterator


def _item_to_triples(item: dict) -> Iterator:
    src = item["id"]

    for relation, tgt_vals in item.items():
        if relation == "id":
            continue

        if isinstance(tgt_vals, list):
            for val in tgt_vals:
                yield (src, relation, val)
        else:
            yield (src, relation, tgt_vals)


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
