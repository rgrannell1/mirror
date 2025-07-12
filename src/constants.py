"""Constant values used throughout the application."""

from typing import cast

from src.mirror_types import VideoEncoding, VideoEncodingConfig


MOSAIC_WIDTH = 2
MOSAIC_HEIGHT = 2
THUMBNAIL_WIDTH = 400
THUMBNAIL_HEIGHT = 400
DATE_FORMAT = "%Y:%m:%d %H:%M:%S"

# Attr-Exif property associations
# these are the exif attributes we care about
EXIF_ATTR_ASSOCIATIONS = {
    "DateTimeOriginal": "created_at",
    "FNumber": "f_stop",
    "FocalLengthIn35mmFilm": "focal_length",
    "Model": "model",
    "ExposureTime": "exposure_time",
    "ISOSpeedRatings": "iso",
    "ExifImageWidth": "width",
    "ExifImageHeight": "height",
}

SUPPORTED_IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".JPG", ".JPEG", ".PNG")

# How should we encode our photos? Currently uses
# - thumbnail: a lossy thumbnail for fast loading
# - full_image_lossless: a lossless webp image for high quality
# - full_image_png: a png image so I can share images to Signal and other non-webp apps
IMAGE_ENCODINGS = [
    ("thumbnail_lossy", {"format": "webp", "quality": 85, "method": 6}),
    ("full_image_lossless", {"format": "webp", "lossless": True}),
    ("full_image_png", {"format": "png", "quality": 100, "method": 6}),
]

# How should we encode our videos? Currently uses unscaled + various
# scaling of libx264 encoding
VIDEO_ENCODINGS: list[VideoEncoding] = [
    (
        "video_libx264_unscaled",
        cast(
            VideoEncodingConfig,
            {
                "bitrate": "30M",
                "width": None,
                "height": None,
            },
        ),
    ),
    (
        "video_libx264_1080p",
        cast(
            VideoEncodingConfig,
            {
                "bitrate": "5000k",
                "width": 1920,
                "height": 1080,
            },
        ),
    ),
    (
        "video_libx264_720p",
        cast(
            VideoEncodingConfig,
            {
                "bitrate": "2500k",
                "width": 1280,
                "height": 720,
            },
        ),
    ),
    (
        "video_libx264_480p",
        cast(
            VideoEncodingConfig,
            {
                "bitrate": "1000k",
                "width": 854,
                "height": 480,
            },
        ),
    ),
]

VIDEO_THUMBNAIL_FORMAT = ".webp"
VIDEO_CONTENT_TYPE = "video/mp4"
ARN_PREFIX = "arn:ró:"
