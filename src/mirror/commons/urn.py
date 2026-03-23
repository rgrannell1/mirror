"""Parse and format mirror media URNs (urn:ró:<noun>:<id>?…)."""

import urllib.parse

from mirror.commons.constants import URN_PREFIX


def is_mirror_urn(value: str) -> bool:
    return value.startswith(URN_PREFIX)


def parse_mirror_urn(urn: str) -> dict:
    if not urn.startswith(URN_PREFIX):
        raise ValueError(f"Invalid URN format: must start with '{URN_PREFIX}', got '{urn}'")

    remainder = urn[len(URN_PREFIX) :]
    if "?" in remainder:
        main_part, query_part = remainder.split("?", 1)
        qs = dict(urllib.parse.parse_qsl(query_part))
    else:
        main_part = remainder
        qs = {}

    if ":" not in main_part:
        raise ValueError(f"Invalid URN format: missing noun:id separator, got '{urn}'")

    noun, id_part = main_part.split(":", 1)

    if not noun:
        raise ValueError(f"Invalid URN format: empty noun, got '{urn}'")
    if not id_part:
        raise ValueError(f"Invalid URN format: empty id, got '{urn}'")

    return {"type": noun, "id": id_part, **qs}


def format_mirror_urn(thing: dict) -> str:
    base_urn = f"{URN_PREFIX}{thing['type']}:{thing['id']}"

    props = {key: val for key, val in thing.items() if key not in ("type", "id")}

    if props:
        query_string = urllib.parse.urlencode(props)
        return f"{base_urn}?{query_string}"

    return base_urn
