"""Model definitions and data classes"""

from mirror.models.mirror_types import IModel, VideoEncodingConfig, VideoEncoding
from mirror.models.photo import (
    PhotoContent,
    EncodedPhotoModel,
    PhotoModel,
    Photo,
    PhotoMetadataModel,
    PhotoMetadataSummaryModel,
)
from mirror.models.video import EncodedVideoModel, VideoModel, Video
from mirror.models.media import IMedia, Media
from mirror.models.exif import PhotoExifData, ExifReader
from mirror.models.album import Album, AlbumMetadataModel, AlbumDataModel
from mirror.models.phash import PhashData, PHashReader

__all__ = [
    "IModel",
    "VideoEncodingConfig",
    "VideoEncoding",
    "PhotoContent",
    "EncodedPhotoModel",
    "PhotoModel",
    "Photo",
    "PhotoMetadataModel",
    "PhotoMetadataSummaryModel",
    "EncodedVideoModel",
    "VideoModel",
    "Video",
    "IMedia",
    "Media",
    "PhotoExifData",
    "ExifReader",
    "Album",
    "AlbumMetadataModel",
    "AlbumDataModel",
    "PhashData",
    "PHashReader",
]
