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

PHOTO_DIRECTORY = "/home/rg/Drive/Media"
DATABASE_PATH = "/home/rg/media.db"
OUTPUT_DIRECTORY = "/home/rg/Code/websites/photos.rgrannell.xyz/manifest"
ALBUM_METADATA_FILE = "home/rg/Code/mirror/src/schemas/album_metadata.json"
