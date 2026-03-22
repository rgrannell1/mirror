"""Various utility functions."""

import hashlib


def deterministic_hash_str(data: str) -> str:
    """Returns a deterministic MD5 hash (10 chars) of a string."""
    return hashlib.md5(data.encode()).hexdigest()[:10]


def deterministic_hash(data: bytes) -> str:
    """Returns a deterministic MD5 hash (10 chars) of bytes.

    Deprecated: Use deterministic_hash_str for strings instead.
    """
    return hashlib.md5(data).hexdigest()[:10]
