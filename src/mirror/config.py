"""Configuration used by the project."""

import os
from dotenv import load_dotenv

load_dotenv()

# S3-Compatible API Credential
SPACES_REGION = os.getenv("SPACES_REGION")
SPACES_ENDPOINT_URL = os.getenv("SPACES_ENDPOINT_URL")
SPACES_BUCKET = os.getenv("SPACES_BUCKET")
SPACES_ACCESS_KEY_ID = os.getenv("SPACES_ACCESS_KEY_ID")
SPACES_SECRET_KEY = os.getenv("SPACES_SECRET_KEY")

DATA_URL = "data:image/bmp;base64,"

# TODO overly hard-coded
PHOTOS_URL = "https://photos-cdn.rgrannell.xyz"

HOME = os.getenv("HOME")
PHOTO_DIRECTORY = f"{HOME}/Drive/Media"
DATABASE_PATH = f"{HOME}/media.db"
OUTPUT_DIRECTORY = f"{HOME}/Code/websites/photos.rgrannell.xyz/manifest"
ALBUM_METADATA_FILE = f"{HOME}/Code/mirror/src/schemas/album_metadata.json"

GEONAMES_USERNAME = os.getenv("GEONAMES_USERNAME")
