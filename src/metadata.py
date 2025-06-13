"""A file for dealing with metadata for albums and photos"""

from typing import Protocol

# Implement readers and writers


class IAlbumMetadataReader(Protocol):
    pass


class IAlbumMetadataWriter(Protocol):
    pass


class IPhotoMetadataReader(Protocol):
    pass


class IPhotoMetadataWriter(Protocol):
    pass
