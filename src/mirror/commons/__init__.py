"""Commons - Shared configuration, utilities, and constants"""

from mirror.commons.config import *
from mirror.commons.constants import *
from mirror.commons.utils import *
from mirror.commons.dates import *
from mirror.commons.ansi import *
from mirror.commons.exceptions import *
from mirror.commons.tables import *

__all__ = [
    # config
    "SPACES_REGION",
    "SPACES_ENDPOINT_URL",
    "SPACES_BUCKET",
    "SPACES_ACCESS_KEY_ID",
    "SPACES_SECRET_KEY",
    "DATA_URL",
    "PHOTOS_URL",
    "HOME",
    "PHOTO_DIRECTORY",
    "DATABASE_PATH",
    "D1_DATABASE_PATH",
    "D1_DUMP_PATH",
    "OUTPUT_DIRECTORY",
    "ALBUM_METADATA_FILE",
    "PHOTO_METADATA_FILE",
    "GEONAMES_USERNAME",
    # constants
    "MOSAIC_WIDTH",
    "MOSAIC_HEIGHT",
    "THUMBNAIL_WIDTH",
    "THUMBNAIL_HEIGHT",
    "DATE_FORMAT",
    "EXIF_ATTR_ASSOCIATIONS",
    "SUPPORTED_IMAGE_EXTENSIONS",
    "IMAGE_ENCODINGS",
    "VIDEO_ENCODINGS",
    "FULL_SIZED_VIDEO_ROLE",
    "VIDEO_THUMBNAIL_FORMAT",
    "VIDEO_CONTENT_TYPE",
    "URN_PREFIX",
    "KnownRelations",
    "KnownTypes",
    "KnownWikiProperties",
    "BINOMIAL_TYPE",
    # utils
    "deterministic_hash",
    "deterministic_hash_str",
    # dates
    "date_range",
    # ansi
    "ANSI",
    # exceptions
    "InvalidVideoDimensionsException",
    "VideoResolutionLookupException",
    "VideoReadException",
    # tables
    "PHOTO_ICON_TABLE",
    "PHOTOS_TABLE",
    "PHASHES_TABLE",
    "VIDEOS_TABLE",
    "EXIF_TABLE",
    "ENCODED_PHOTOS_TABLE",
    "ENCODED_VIDEO_TABLE",
    "ALBUM_CONTENTS_VIEW",
    "ALBUM_DATA_VIEW",
    "PHOTO_DATA_VIEW",
    "VIDEO_DATA_VIEW",
    "PHOTO_METADATA_TABLE",
    "PHOTO_METADATA_VIEW",
    "PHOTO_METADATA_SUMMARY",
    "GEONAME_TABLE",
    "BINOMIALS_WIKIDATA_ID_TABLE",
    "WIKIDATA_TABLE",
    "SOCIAL_CARD_TABLE",
]
