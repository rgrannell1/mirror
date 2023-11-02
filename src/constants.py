"""Various constants used throughout this project"""

import re

ATTR_ALBUM_TITLE = 'user.xyz.rgrannell.photos.album_title'
ATTR_ALBUM_ID = 'user.xyz.rgrannell.photos.album_id'
ATTR_ALBUM_COVER = 'user.xyz.rgrannell.photos.album_cover'
ATTR_TAG = 'user.xyz.rgrannell.photos.tags'

THUMBNAIL_WIDTH = 400
THUMBNAIL_HEIGHT = 400

TITLE_PATTERN = re.compile(r'!\[(.*?)\]')
