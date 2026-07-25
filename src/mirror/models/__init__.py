"""Model definitions and data classes"""

from mirror.models.album import Album, AlbumDataModel, AlbumMetadataModel
from mirror.models.exif import ExifReader, PhotoExifData
from mirror.models.media import IMedia, Media
from mirror.models.mirror_types import IModel, VideoEncoding, VideoEncodingConfig
from mirror.models.phash import PhashData, PHashReader
from mirror.models.photo import (
    EncodedPhotoModel,
    Photo,
    PhotoContent,
    PhotoMetadataModel,
    PhotoMetadataSummaryModel,
    PhotoModel,
)
from mirror.models.video import EncodedVideoModel, Video, VideoModel

__all__ = [
    "Album",
    "AlbumDataModel",
    "AlbumMetadataModel",
    "EncodedPhotoModel",
    "EncodedVideoModel",
    "ExifReader",
    "IMedia",
    "IModel",
    "Media",
    "PHashReader",
    "PhashData",
    "Photo",
    "PhotoContent",
    "PhotoExifData",
    "PhotoMetadataModel",
    "PhotoMetadataSummaryModel",
    "PhotoModel",
    "Video",
    "VideoEncoding",
    "VideoEncodingConfig",
    "VideoModel",
]
