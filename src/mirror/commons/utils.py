"""Various utility functions."""

import hashlib
from pathlib import Path
from typing import Optional

from mirror.commons.config import PHOTOS_URL
from mirror.commons.constants import MISCELLANEOUS_ALBUM_NAME


def is_miscellaneous_dpath(dpath: str) -> bool:
    """True for a hidden Miscellaneous album folder or its Published subfolder."""
    path = Path(dpath)
    return MISCELLANEOUS_ALBUM_NAME in {path.name, path.parent.name}


def short_cdn_url(url: Optional[str]) -> str:
    """Strip CDN base URL for compact triple targets."""
    return url.replace(PHOTOS_URL, "") if url else ""


def deterministic_hash_str(data: str) -> str:
    """Returns a deterministic MD5 hash (10 chars) of a string."""
    return hashlib.md5(data.encode()).hexdigest()[:10]


def deterministic_hash(data: bytes) -> str:
    """Returns a deterministic MD5 hash (10 chars) of bytes.

    Deprecated: Use deterministic_hash_str for strings instead.
    """
    return hashlib.md5(data).hexdigest()[:10]
