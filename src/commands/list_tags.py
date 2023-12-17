
import json

from src.photo import PhotoVault
from src.constants import ATTR_TAG

def list_tags(dir: str):
  """List all tags in all images in the directory, as a series
     of JSON objects"""
  tag_set = {}

  for image in PhotoVault(dir).list_images():
    tags = image.get_metadata()

    if ATTR_TAG not in tags:
      continue

    for tag in tags[ATTR_TAG]:
      if tag not in tag_set:
        tag_set[tag] = 1

      tag_set[tag] += 1

  for tag, count in tag_set.items():
    if tag == '':
      continue

    print(json.dumps({
      'tag': tag,
      'count': count
    }))
