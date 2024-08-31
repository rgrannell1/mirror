"""Classes for dealing with tag-files, and tag metadata-files"""

import os
import json
import yaml
import jsonschema
from src.album import Album
from typing import Dict, List, Optional

from src.constants import (ATTR_ALBUM_PERMALINK, ATTR_ALBUM_TITLE, ATTR_ALBUM_DESCRIPTION,
                           ATTR_ALBUM_COVER, ATTR_ALBUM_GEOLOCATION,
                           ATTR_ALBUM_ID, ATTR_BLUR, ATTR_SHARE_AUDIO, ATTR_SHUTTER_SPEED, ATTR_TAG,
                           ATTR_DESCRIPTION)
from src.video import Video

current_dir = os.path.dirname(os.path.abspath(__file__))
schema_path = os.path.join(current_dir, "../schemas", "tagfile.json")


class Tagfile:
  """Represents a Tagfile in a directory of images"""

  def __init__(self, dirname: str, metadata_path, images: List, videos: List[Video]) -> None:
    self.dirname = dirname
    self.images = images
    self.metadata_path = metadata_path
    self.videos = videos

  def id(self) -> str:
    """Compute a directory-specific tagfile ID"""

    return str(hash(self.dirname))

  def album_data(self) -> str:
    """Given a series of images, and a directory, return the content of a tagfile."""

    images = {}

    album = Album(self.dirname)
    album_md = album.get_metadata()

    for image in self.images:
      name = image.name()
      transclusion = f"![{name}]({name})"

      image_md = image.get_metadata()
      if not image_md:
        image_md = {}

      tags = list({tag for tag in image_md.get(ATTR_TAG, set()) if tag})

      # properties written back to the tagfile for an image
      images[transclusion] = {
          ATTR_TAG: tags,
          ATTR_DESCRIPTION: image.get_xattr_description()
      }

    videos = {}

    for video in self.videos:
      name = video.name()
      transclusion = f"![{name}]({name})"

      videos[transclusion] = {
          ATTR_TAG: list(video.get_xattr_tags()),
          ATTR_DESCRIPTION: video.get_xattr_description(),
          ATTR_SHARE_AUDIO: video.get_xattr_share_audio(),
      }

    return [{
        ATTR_ALBUM_TITLE:
        album_md.title if album_md and album_md.title else self.dirname,
        ATTR_ALBUM_COVER:
        album_md.cover if album_md and album_md.cover else 'Cover',
        ATTR_ALBUM_DESCRIPTION:
        album_md.description if album_md and album_md.description else "",
        ATTR_ALBUM_ID:
        self.id(),
        ATTR_ALBUM_GEOLOCATION:
        album_md.geolocation if album_md and album_md.geolocation else "",
        ATTR_ALBUM_PERMALINK:
        album_md.permalink if album_md and album_md.permalink else "",
        'images':
        images,
        'videos': videos
    }]

  def to_yaml(self) -> str:
    return yaml.dump(self.album_data())

  def write(self) -> None:
    """Write a tagfile to the current directory."""

    tag_path = f"{self.dirname}/tags.md"

    # write the tagfile content to the directory
    with open(tag_path, "w") as conn:
      conn.write(self.to_yaml())

  @classmethod
  def read(kls, fpath: str) -> Optional[Dict]:
    """Read a tagfile, and yield each image and its associated tags."""

    with open(schema_path) as conn:
      tag_schema = json.load(conn)

    with open(fpath, 'r') as conn:
      yaml_data = yaml.safe_load(conn)
      if not yaml_data:
        return None

    try:
      jsonschema.validate(instance=yaml_data[0], schema=tag_schema)
      tag_file = yaml_data[0]
    except Exception as err:
      raise Exception(f"Error reading tagfile {fpath}") from err

    cover = os.path.basename(tag_file[ATTR_ALBUM_COVER])
    dirpath = os.path.dirname(fpath)

    if f'![{cover}]({cover})' not in tag_file['images'] and cover != 'Cover' and cover != 'Unknown':
      raise Exception(f"{cover} is not present in the album {dirpath}")

    return tag_file
