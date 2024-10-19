"""Various constants used throughout this project"""

import re

DB_PATH = "/home/rg/.mirror-manifest.db"

MAX_DELETION_LIMIT = 50

# Album Attributes
ATTR_ALBUM_TITLE = "user.xyz.rgrannell.photos.album_title"
ATTR_ALBUM_ID = "user.xyz.rgrannell.photos.album_id"
ATTR_ALBUM_COVER = "user.xyz.rgrannell.photos.album_cover"
ATTR_ALBUM_DESCRIPTION = "user.xyz.rgrannell.photos.album_description"
ATTR_ALBUM_GEOLOCATION = "user.xyz.rgrannell.photos.geolocation"
ATTR_ALBUM_PERMALINK = "user.xyz.rgrannell.photos.permalink"

# The set of attributes associated with an album
SET_ATTR_ALBUM = {
    ATTR_ALBUM_ID,
    ATTR_ALBUM_TITLE,
    ATTR_ALBUM_COVER,
    ATTR_ALBUM_DESCRIPTION,
    ATTR_ALBUM_GEOLOCATION,
    ATTR_ALBUM_PERMALINK,
}

# Photo Attributes
ATTR_TAG = "user.xyz.rgrannell.photos.tags"
ATTR_DESCRIPTION = "user.xyz.rgrannell.photos.description"
ATTR_DATE_TIME = "user.xyz.rgrannell.photos.date_time"
ATTR_BLUR = "user.xyz.rgrannell.photos.blur"
ATTR_SHUTTER_SPEED = "user.xyz.rgrannell.photos.shutter_speed"

# Video Attributes
ATTR_SHARE_AUDIO = "user.xyz.rgrannell.photos.share_audio"

# Photo Settings
ATTR_FSTOP = "user.xyz.rgrannell.photos.fstop"
ATTR_FOCAL_EQUIVALENT = "user.xyz.rgrannell.photos.focal_equivalent"
ATTR_MODEL = "user.xyz.rgrannell.photos.model"
ATTR_ISO = "user.xyz.rgrannell.photos.iso"

# Dimensions
ATTR_WIDTH = "user.xyz.rgrannell.photos.width"
ATTR_HEIGHT = "user.xyz.rgrannell.photos.height"

# Geolocation
ATTR_LOCATION_ADDRESS = "user.xyz.rgrannell.photos.location_address"
ATTR_LOCATION_LATITUDE = "user.xyz.rgrannell.photos.location_latitude"
ATTR_LOCATION_LONGITUDE = "user.xyz.rgrannell.photos.location_longitude"

# Thumnail Dimensions
THUMBNAIL_WIDTH = 400
THUMBNAIL_HEIGHT = 400

MOSAIC_WIDTH = 2
MOSAIC_HEIGHT = 2

# Output Date Format
DATE_FORMAT = "%Y:%m:%d %H:%M:%S"

TITLE_PATTERN = re.compile(r"!\[(.*?)\]")

# URLs
PERSONAL_URL = "https://rgrannell.xyz"
PHOTOS_URL = "https://photos.rgrannell.xyz"

# Attr-Exif Property Associations
EXIF_ATTR_ASSOCIATIONS = [
    (ATTR_DATE_TIME, "DateTimeOriginal"),
    (ATTR_FSTOP, "FNumber"),
    (ATTR_FOCAL_EQUIVALENT, "FocalLengthIn35mmFilm"),
    (ATTR_MODEL, "Model"),
    (ATTR_SHUTTER_SPEED, "ExposureTime"),
    (ATTR_ISO, "ISOSpeedRatings"),
    (ATTR_WIDTH, "ExifImageWidth"),
    (ATTR_HEIGHT, "ExifImageHeight"),
]

# Author
AUTHOR = "R* Grannell"

# Thumbnail encodings
THUMBNAIL_ENCODINGS = [
    ("thumbnail_lossless", {"format": "webp", "lossless": True}),
    ("thumbnail_lossy", {"format": "jpeg"}),
    ("thumbnail_lossy_v2", {"format": "webp", "quality": 85, "method": 6}),
]

# Full sized image encodings
IMAGE_ENCODINGS = [
    ("full_image_lossless", {"format": "webp", "lossless": True}),
    ("full_image_lossy", {"format": "webp"}),
]

VIDEO_ENCODINGS = [
    (
        "video_libx264_unscaled",
        {
            "bitrate": "30M",
            "width": None,
            "height": None,
        },
    ),
    (
        "video_libx264_1080p",
        {
            "bitrate": "5000k",
            "width": 1920,
            "height": 1080,
        },
    ),
    (
        "video_libx264_720p",
        {
            "bitrate": "2500k",
            "width": 1280,
            "height": 720,
        },
    ),
    (
        "video_libx264_480p",
        {
            "bitrate": "1000k",
            "width": 854,
            "height": 480,
        },
    ),
]
