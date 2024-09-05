import os
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

    def get_xattr_share_audio(self) -> bool:
        """Should the audio also be shared?"""

        return True if self.get_xattr_attr(ATTR_SHARE_AUDIO) == "true" else False

    def get_resolution(self) -> Optional[Tuple[int, int]]:
        probe = ffmpeg.probe(self.path)
        video_streams = [
            stream for stream in probe["streams"] if stream["codec_type"] == "video"
        ]

        if len(video_streams) > 0:
            width = int(video_streams[0]["width"])
            height = int(video_streams[0]["height"])

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
                    self.set_xattr_attr(attr, ", ".join(value))
                elif attr == ATTR_SHARE_AUDIO:
                    self.set_xattr_attr(attr, "true" if value else "false")
                else:
                    self.set_xattr_attr(attr, value)
            except Exception as err:
                raise ValueError(f"failed to set {attr} to {value} on image") from err

    def encode_video(
        self,
        upload_file_name: str,
        video_bitrate: str,
        width: Optional[int],
        height: Optional[int],
        share_audio: bool = False,
    ) -> Tuple[str, str]:
        """Encode the video"""

        actual_width, actual_height = self.get_resolution()
        if (
            actual_width
            and actual_height
            and width
            and height
            and (actual_width < width or actual_height < height)
        ):
            return

        VIDEO_CODEC = "libx264"

        input_args = {}
        kwargs = {
            "vcodec": VIDEO_CODEC,
            "video_bitrate": video_bitrate,
            "strict": "-2",
            "movflags": "+faststart",
            "preset": "slow",
            "format": "mp4",
            "loglevel": "info",
        }

        if share_audio:
            kwargs["acodec"] = "aac"
        else:
            input_args["an"] = None

        if width and height:
            kwargs["vf"] = f"scale={width}:{height}"

        fpath = f"/tmp/mirror/{upload_file_name}"

        os.makedirs(os.path.dirname(fpath), exist_ok=True)

        try:
            os.remove(fpath)
        except FileNotFoundError:
            pass

        (
            ffmpeg
            .input(self.path, **input_args)
            .output(fpath, **kwargs)
            .run()
        )

        return fpath
