"""Various utility functions."""

import hashlib


def deterministic_hash(data: bytes) -> str:
    """Returns a deterministic hash of the data."""

    return hashlib.md5(data).hexdigest()[:10]


def deterministic_hash_str(data: str) -> str:
    """Returns a deterministic hash of a data string"""

    return deterministic_byte_hash(data.encode())


def deterministic_byte_hash(data: bytes) -> str:
    """Returns a deterministic hash of data bytes"""

    return hashlib.md5(data).hexdigest()[:10]
