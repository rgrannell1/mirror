import ffmpeg
from src.album import Album
from src.media import Media

from typing import Dict
from src.tags import Tags

class Video(Media):
  """A video file."""

  def __init__(self, path: str, metadata_path: str):
    self.path = path
    self.tag_metadata = Tags(metadata_path)

  def encode_video(self) -> Dict:
    pass
    # stabilise and convert

  def get_exif_metadata(self) -> Dict:
    return {}

  def set_metadata(self, attrs, album):
    Album(album.fpath).set_xattrs(album.attrs)

    # TODO implement this! Set description at least.
