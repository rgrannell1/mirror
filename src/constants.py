"""Various constants used throughout this project"""

import re
from src.config import SPACES_BUCKET

SPACES_DOMAIN = f'https://{SPACES_BUCKET}.ams3.cdn.digitaloceanspaces.com/'

# Album Attributes
ATTR_ALBUM_TITLE = 'user.xyz.rgrannell.photos.album_title'
ATTR_ALBUM_ID = 'user.xyz.rgrannell.photos.album_id'
ATTR_ALBUM_COVER = 'user.xyz.rgrannell.photos.album_cover'

# Photo Attributes
ATTR_TAG = 'user.xyz.rgrannell.photos.tags'
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

TITLE_PATTERN = re.compile(r'!\[(.*?)\]')
