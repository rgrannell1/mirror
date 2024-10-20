import hashlib
from typing import Dict


def deterministic_hash(data: str) -> str:
    return hashlib.md5(data.encode()).hexdigest()[:10]


def deterministic_byte_hash(data: bytes) -> str:
    return hashlib.md5(data).hexdigest()[:10]


def deterministic_hash_attrs(data: Dict) -> str:
    items = sorted(list(data.items()), key=lambda pair: pair[0])
    hasheable = []

    for key, value in items:
        if isinstance(value, list):
            hasheable.append(f"{key}={''.join(value)}")
        else:
            hasheable.append(f"{key}={str(value)}")

    return deterministic_hash("".join(hasheable))
