"""Configuration used by the project."""

import os

from dotenv import load_dotenv

load_dotenv()

# S3-Compatible API Credentials
SPACES_REGION = os.getenv("SPACES_REGION")
SPACES_ENDPOINT_URL = os.getenv("SPACES_ENDPOINT_URL")
SPACES_BUCKET = os.getenv("SPACES_BUCKET")
SPACES_ACCESS_KEY_ID = os.getenv("SPACES_ACCESS_KEY_ID")
SPACES_SECRET_KEY = os.getenv("SPACES_SECRET_KEY")

DATA_URL = "data:image/bmp;base64,"

# Photo CDN URL
PHOTOS_URL = os.getenv("PHOTOS_URL", "https://photos-cdn.rgrannell.xyz")

HOME = os.getenv("HOME", os.path.expanduser("~"))

# Media and database paths (configurable via environment)
PHOTO_DIRECTORY = os.getenv("PHOTO_DIRECTORY", f"{HOME}/Drive/Media")
DATABASE_PATH = os.getenv("DATABASE_PATH", f"{HOME}/media.db")
D1_DATABASE_PATH = os.getenv("D1_DATABASE_PATH", f"{HOME}/media_d1.db")
D1_DUMP_PATH = os.getenv("D1_DUMP_PATH", f"{HOME}/media_d1.sql")
WEBSITE_DIRECTORY = os.getenv("WEBSITE_DIRECTORY", f"{HOME}/Code/websites/photos.rgrannell.xyz")
OUTPUT_DIRECTORY = os.getenv("OUTPUT_DIRECTORY", f"{HOME}/Code/websites/photos.rgrannell.xyz/manifest")

# Schema file paths (relative to project root if needed)
_SCHEMA_DIR = os.getenv("MIRROR_SCHEMA_DIR", f"{HOME}/Code/mirror/src/mirror/schemas")
ALBUM_METADATA_FILE = os.path.join(_SCHEMA_DIR, "album_metadata.json")
PHOTO_METADATA_FILE = os.path.join(_SCHEMA_DIR, "photo_metadata.json")

GEONAMES_USERNAME = os.getenv("GEONAMES_USERNAME")

# Path to the badger binary (local build has --json-progress; system package does not)
BADGER_PATH = os.getenv("BADGER_PATH", f"{HOME}/Code/badger/badger")

# Default camera DCIM path when connected via USB
CAMERA_DCIM_DEFAULT = os.getenv("CAMERA_DCIM", f"/media/{os.getenv('USER', 'rg')}/PROGRADE/DCIM")

# Staging directory for camera imports before badger clustering
RAW_MEDIA_DIRECTORY = os.getenv("RAW_MEDIA_DIRECTORY", f"{HOME}/RawMedia")
