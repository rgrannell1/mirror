"""Types shared across the project"""

from dataclasses import dataclass
from typing import Dict


@dataclass
class TagfileAlbumConfiguration:
    """Tagfile information about an album"""

    fpath: str
    attrs: Dict


@dataclass
class TagfileImageConfiguration:
    """Tagfile information about an image"""

    fpath: str
    album: TagfileAlbumConfiguration
    attrs: Dict


@dataclass
class TagfileVideoConfiguration:
    """Tagfile information about a video"""

    fpath: str
    album: TagfileAlbumConfiguration
    attrs: Dict


@dataclass
class ImageContent:
    """A dataclass representing an images content"""

    hash: str
    content: bytes
