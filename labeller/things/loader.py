"""Load and cache the raw things.toml data."""

import tomllib
from functools import cache
from pathlib import Path

THINGS_PATH = Path(__file__).parent.parent.parent / "things.toml"


@cache
def load_raw() -> dict:
    raw = THINGS_PATH.read_text(encoding="utf-8")
    # [[`]] is used as a header in the first places entry — invalid TOML.
    cleaned = raw.replace("[[`]]", "[[places]]")
    return tomllib.loads(cleaned)
