import ffmpeg
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
