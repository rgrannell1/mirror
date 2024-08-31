import ffmpeg
from src.album import Album
from src.constants import ATTR_TAG
from src.media import Media

from typing import Dict
from src.tags import Tags

class Video(Media):
  """A video file."""

  def __init__(self, path: str, metadata_path: str):
    self.path = path
    self.tag_metadata = Tags(metadata_path)

  def get_exif_metadata(self) -> Dict:
    """Exif support is not available for videos"""
    return {}

  def set_metadata(self, attrs, album):
    """set metadata as xattrs on the video"""
    Album(album.fpath).set_xattrs(album.attrs)

    for attr, value in attrs.items():
      if value is None:
        continue

      try:
        if attr == ATTR_TAG:
          self.set_xattr_attr(attr, ', '.join(value))
      except Exception as err:
        raise ValueError(f"failed to set {attr} to {value} on image") from err

  def encode_video(self, video_bitrate: str, width: int, height: int, disable_audio: bool = False) -> str:
    """Encode the video"""

    VIDEO_CODEC = 'libx265'
    kwargs = {
      "vcodec": VIDEO_CODEC,
      "video_bitrate": video_bitrate,
      "vf": f'scale={width}:{height}',
      "acodec": 'aac' if not disable_audio else 'an',
      "strict": '-2',
      "movflags": '+faststart',
      "preset": 'slow',
      "tune": 'film',
      "format": 'mp4'
    }

    fpath = '/tmp/mirror-encoded-video.mp4'
    (
        ffmpeg
        .input(self.path)
        .output(fpath, **kwargs)
        .run()
    )

    return fpath
