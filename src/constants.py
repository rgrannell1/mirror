"""Various constants used throughout this project"""

import re
from src.config import SPACES_BUCKET

DB_PATH = '/home/rg/.mirror-manifest.db'
SPACES_DOMAIN = f'https://{SPACES_BUCKET}.ams3.cdn.digitaloceanspaces.com/'

# Album Attributes
ATTR_ALBUM_TITLE = 'user.xyz.rgrannell.photos.album_title'
ATTR_ALBUM_ID = 'user.xyz.rgrannell.photos.album_id'
ATTR_ALBUM_COVER = 'user.xyz.rgrannell.photos.album_cover'
ATTR_ALBUM_DESCRIPTION = 'user.xyz.rgrannell.photos.album_description'
ATTR_ALBUM_GEOLOCATION = 'user.xyz.rgrannell.photos.geolocation'

# The set of attributes associated with an album
SET_ATTR_ALBUM = {
  ATTR_ALBUM_ID,
  ATTR_ALBUM_TITLE,
  ATTR_ALBUM_COVER,
  ATTR_ALBUM_DESCRIPTION,
  ATTR_ALBUM_GEOLOCATION
}

# Photo Attributes
ATTR_TAG = 'user.xyz.rgrannell.photos.tags'
ATTR_DESCRIPTION = 'user.xyz.rgrannell.photos.description'
ATTR_DATE_TIME = 'user.xyz.rgrannell.photos.date_time'

# Photo Settings
ATTR_FSTOP = 'user.xyz.rgrannell.photos.fstop'
ATTR_FOCAL_EQUIVALENT = 'user.xyz.rgrannell.photos.focal_equivalent'
ATTR_MODEL = 'user.xyz.rgrannell.photos.model'
ATTR_ISO = 'user.xyz.rgrannell.photos.iso'

# Dimensions
ATTR_WIDTH = 'user.xyz.rgrannell.photos.width'
ATTR_HEIGHT = 'user.xyz.rgrannell.photos.height'

# Geolocation
ATTR_LOCATION_ADDRESS = 'user.xyz.rgrannell.photos.location_address'
ATTR_LOCATION_LATITUDE = 'user.xyz.rgrannell.photos.location_latitude'
ATTR_LOCATION_LONGITUDE = 'user.xyz.rgrannell.photos.location_longitude'

# Thumnail Dimensions
THUMBNAIL_WIDTH = 400
THUMBNAIL_HEIGHT = 400

# Output Date Format
DATE_FORMAT = "%Y:%m:%d %H:%M:%S"

TITLE_PATTERN = re.compile(r'!\[(.*?)\]')

# URLs
PERSONAL_URL = "https://rgrannell.xyz"
PHOTOS_URL = "https://photos.rgrannell.xyz"

# Attr-Exif Property Associations
EXIF_ATTR_ASSOCIATIONS = [
  (ATTR_DATE_TIME, 'DateTimeOriginal'),
  (ATTR_FSTOP, 'FNumber'),
  (ATTR_FOCAL_EQUIVALENT, 'FocalLengthIn35mmFilm'),
  (ATTR_MODEL, 'Model'),
  (ATTR_ISO, 'PhotographicSensitivity'),
  (ATTR_WIDTH, 'ExifImageWidth'),
  (ATTR_HEIGHT, 'ExifImageHeight')
]

# Author
AUTHOR = 'Róisín Grannell'
