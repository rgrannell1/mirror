"""A file for dealing with metadata for albums and photos"""

from typing import Iterator, Protocol

from src.album import AlbumMetadataModel
from src.photo import PhotoMetadataModel

# Protocols defining how metadata can be communicated to/from other locations
class IAlbumMetadataReader(Protocol):
    def list_album_metadata(self) -> Iterator[AlbumMetadataModel]: ...


class IAlbumMetadataWriter(Protocol):
    def write_album_metadata(self) -> None: ...


class IPhotoMetadataReader(Protocol):
    def list_photo_metadata(self) -> Iterator[PhotoMetadataModel]: ...


class IPhotoMetadataWriter(Protocol):
    def write_photo_metadata(self) -> None: ...
