
import json

from src.photo import PhotoVault
from src.constants import ATTR_TAG

def list_photos(dir: str, tag: str):
  """List all photos in the directory, as a series of JSON objects. If
     a tag is specified, only list photos with that tag"""

  for image in PhotoVault(dir).list_images():
    attrs = image.has_metadata()

    if tag and tag not in attrs.get(ATTR_TAG, []):
      continue

    if ATTR_TAG in attrs:
      attrs[ATTR_TAG] = list(attrs[ATTR_TAG])

    print(json.dumps({
      'fpath': image.path,
      'attrs': attrs
    }))
