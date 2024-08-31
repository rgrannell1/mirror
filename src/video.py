import os
import time
import ffmpeg
from src.album import Album
from src.constants import ATTR_SHARE_AUDIO, ATTR_TAG
from src.media import Media

from typing import Dict, Optional, Tuple
from src.tags import Tags

class Video(Media):
  """A video file."""

  def __init__(self, path: str, metadata_path: str):
    self.path = path
    self.tag_metadata = Tags(metadata_path)

  def get_exif_metadata(self) -> Dict:
    """Exif support is not available for videos"""
    return {}

  def get_xattr_share_audio(self) -> Optional[bool]:
    return bool(self.get_xattr_attr(ATTR_SHARE_AUDIO))

  def get_resolution(self) -> Optional[Tuple[int, int]]:
    probe = ffmpeg.probe(self.path)
    video_streams =  [stream for stream in probe['streams'] if stream['codec_type'] == 'video']

    if len(video_streams) > 0:
      width = int(video_streams[0]['width'])
      height = int(video_streams[0]['height'])

      return width, height
    else:
      return None, None

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

  def encode_video(self, video_bitrate: str, width: Optional[int], height: Optional[int], disable_audio: bool = False) -> Tuple[str, str]:
    """Encode the video"""

    actual_width, actual_height = self.get_resolution()
    if actual_width and actual_height and width and height and (actual_width < width or actual_height < height):
      return

    VIDEO_CODEC = 'libx264'

    kwargs = {
      "vcodec": VIDEO_CODEC,
      "video_bitrate": video_bitrate,
      "acodec": 'aac' if not disable_audio else 'an',
      "strict": '-2',
      "movflags": '+faststart',
      "preset": 'veryslow',
      "format": 'mp4'
    }

    if width and height:
      kwargs['vf'] = f'scale={width}:{height}'

    fpath = '/tmp/mirror-encoded-video.mp4'

    try:
      os.remove(fpath)
    except FileNotFoundError:
      pass

    (
        ffmpeg
        .input(self.path)
        .output(fpath, **kwargs)
        .run()
    )

    return fpath
