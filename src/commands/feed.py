
import json

from src.photo import PhotoVault
from src.constants import ATTR_TAG
from src.syndications import JSONFeed

def feed(dir: str, metadata_path: str, feed: str):
  """Generates a JSON feed for the given directory."""

  vault = PhotoVault(dir, '')

  albums = vault.list_albums()

  feed = JSONFeed.feed(albums)
