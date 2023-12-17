"""Classes for dealing with tag-files, and tag metadata-files"""

import os
import json
import yaml
import shutil
import datetime
import jsonschema
from src.album import Album
from src.tags import Tags

from src.constants import (
  ATTR_ALBUM_TITLE,
  ATTR_ALBUM_COVER,
  ATTR_ALBUM_ID,
  ATTR_TAG
)

current_dir = os.path.dirname(os.path.abspath(__file__))
schema_path = os.path.join(current_dir, "../schemas", "tagfile.json")


class Tagfile:
  """Represents a Tagfile in a directory of images"""

  def __init__(self, dirname: str, metadata_path, images) -> None:
    self.dirname = dirname
    self.images = images
    self.metadata_path = metadata_path

  def id(self):
    return str(hash(self.dirname))

  def content(self) -> str:
    """Given a series of images, and a directory, return the content of a tagfile."""

    images = {}

    album = Album(self.dirname)
    album_md = album.get_metadata()

    if not album_md:
      album_md = {}

    for image in self.images:
      name = image.name()
      transclusion = f"![{name}]({name})"

      image_md = image.get_metadata()
      if not image_md:
        image_md = {}

      expander = Tags(self.metadata_path)
      tags = list({tag for tag in image_md.get(ATTR_TAG, set()) if tag})

      images[transclusion] = {
        ATTR_TAG: expander.expand(tags)
      }

    tag_file = [{
      ATTR_ALBUM_TITLE: album_md.get('title', self.dirname),
      ATTR_ALBUM_COVER: album_md.get('cover', 'Cover'),
      ATTR_ALBUM_ID: self.id(),
      'images': images
    }]

    return yaml.dump(tag_file)

  def write(self) -> None:
    """Write a tagfile to the current directory."""

    content = self.content()

    tag_path = f"{self.dirname}/tags.md"

    # backup any existing tagfile
    if os.path.exists(tag_path):
      now = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

      new_tag_path = f"{tag_path}-{now}"
      shutil.move(tag_path, new_tag_path)

    # write the tagfile content to the directory
    with open(tag_path, "w") as conn:
      conn.write(content)

  @classmethod
  def read(kls, fpath):
    """Read a tagfile, and yield each image and its associated tags."""

    with open(schema_path) as conn:
      tag_schema = json.load(conn)

    with open(fpath, 'r') as conn:
      yaml_data = yaml.safe_load(conn)

    jsonschema.validate(instance=yaml_data[0], schema=tag_schema)
    tag_file = yaml_data[0]

    cover = tag_file[ATTR_ALBUM_COVER]
    dirpath = os.path.dirname(fpath)

    if f'![{cover}]({cover})' not in tag_file['images'] and cover != 'Cover':
      raise Exception(f"{cover} is not present in the album {dirpath}")

    return tag_file
