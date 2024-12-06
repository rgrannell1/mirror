"""Constant values used throughout the application."""

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
