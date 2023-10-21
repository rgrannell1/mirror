
import json

from src.photo import PhotoDirectory, Photo
from src.tags import Tagfile, TagMetadata
from .constants import ATTR_TAG

def init(dir: str):
  for dirname, images in PhotoDirectory(dir).list_by_folder().items():
    Tagfile(dirname, images).write()

def tag(dir: str, metadata_path: str):
  for entry in PhotoDirectory(dir).list_tagfiles():
    fpath = entry['fpath']
    attrs = entry['attrs']

    tag_metadata = TagMetadata(metadata_path)

    Photo(fpath).set_metadata(attrs, tag_metadata)

def list_tags(dir: str):
  tag_set = {}

  for image in PhotoDirectory(dir).list():
    tags = image.get_metadata()

    if ATTR_TAG not in tags:
      continue

    for tag in tags[ATTR_TAG]:
      if tag not in tag_set:
        tag_set[tag] = 1

      tag_set[tag] += 1

  for tag, count in tag_set.items():
    print(json.dumps({
      'tag': tag,
      'count': count
    }))
