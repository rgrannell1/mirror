"""Encode video and images"""

import io
import os
from constants import MOSAIC_HEIGHT, MOSAIC_WIDTH, THUMBNAIL_HEIGHT, THUMBNAIL_WIDTH
import cv2
import ffmpeg
from exceptions import (
    InvalidVideoDimensionsException,
    VideoReadException,
    VideoResolutionLookupException,
)
from PIL import Image, ImageOps

from typing import Dict, Optional, Tuple
from photo import PhotoContent


class PhotoEncoder:
    @classmethod
    def encode(self, fpath: str, params: Dict) -> PhotoContent:
        """Encode an image as Webp, and remove EXIF data"""

        img = Image.open(fpath)
        rgb = img.convert("RGB")

        # remove EXIF data from the image by cloning
        data = list(rgb.getdata())
        no_exif = Image.new(rgb.mode, rgb.size)
        no_exif.putdata(data)

        with io.BytesIO() as output:
            # return the image hash and contents

            no_exif.save(output, **params)
            contents = output.getvalue()

            return PhotoContent(contents)

    @classmethod
    def encode_image_mosaic(self, fpath: str) -> PhotoContent:
        """Create a small image to use as a data-url while the main image loads"""

        img = Image.open(fpath)
        rgb = img.convert("RGB")

        # reduce the dimensions of the image to the thumbnail size
        thumb = ImageOps.fit(rgb, (THUMBNAIL_WIDTH, THUMBNAIL_HEIGHT))

        # remove EXIF data from the image by cloning
        data = list(thumb.getdata())
        no_exif = Image.new(thumb.mode, thumb.size)
        no_exif.putdata(data)

        # resize down to a tiny mosaic data-url that can be used to
        # "progressively render" a photo.
        smaller = no_exif.resize((MOSAIC_WIDTH, MOSAIC_HEIGHT), resample=Image.Resampling.BILINEAR)

        with io.BytesIO() as output:
            smaller.save(output, format="bmp", lossless=True)
            return PhotoContent(output.getvalue())

    @classmethod
    def encode_thumbnail(self, fpath: str, params: Dict) -> PhotoContent:
        """Encode a image as a thumbnail, and remove EXIF data"""

        img = Image.open(fpath)
        rgb = img.convert("RGB")

        # reduce the dimensions of the image to the thumbnail size
        thumb = ImageOps.fit(rgb, (THUMBNAIL_WIDTH, THUMBNAIL_HEIGHT))

        # remove EXIF data from the image by cloning
        data = list(thumb.getdata())
        no_exif = Image.new(thumb.mode, thumb.size)
        no_exif.putdata(data)

        with io.BytesIO() as output:
            # return the image hash and contents

            no_exif.save(output, **params)
            return PhotoContent(output.getvalue())


class VideoEncoder:
    """Encode & interact with video"""

    @classmethod
    def encode(
        cls,
        fpath: str,
        upload_file_name: str,
        video_bitrate: str,
        width: Optional[int],
        height: Optional[int],
        share_audio: bool = False,
    ) -> Optional[str]:
        """Encode the video"""

        actual_width, actual_height = cls.resolution(fpath)
        if actual_width and actual_height and width and height and (actual_width < width or actual_height < height):
            raise InvalidVideoDimensionsException("Video is too small to encode")

        VIDEO_CODEC = "libx264"

        input_args: Dict = {}
        kwargs = {
            "vcodec": VIDEO_CODEC,
            "video_bitrate": video_bitrate,
            "strict": "-2",
            "movflags": "+faststart",
            "preset": "slow",
            "format": "mp4",
            "loglevel": "error",
        }

        if share_audio:
            kwargs["acodec"] = "aac"
        else:
            input_args["an"] = None

        if width and height:
            kwargs["vf"] = f"scale={width}:{height}"

        output_fpath = f"/tmp/mirror/{upload_file_name}"

        os.makedirs(os.path.dirname(output_fpath), exist_ok=True)

        # prevent accidental upload of old file
        try:
            os.remove(output_fpath)
        except FileNotFoundError:
            pass

        (ffmpeg.input(fpath, **input_args).output(output_fpath, **kwargs).run())

        return output_fpath

    @classmethod
    def resolution(self, fpath: str) -> Tuple[int, int]:
        """Encode a video"""
        "Returns resolution of the video, if it's possible to determine?"

        probe = ffmpeg.probe(fpath)
        video_streams = [stream for stream in probe["streams"] if stream["codec_type"] == "video"]

        if video_streams:
            width = int(video_streams[0]["width"])
            height = int(video_streams[0]["height"])

            return width, height

        raise VideoResolutionLookupException(f"Failed to determine resolution of {fpath}")

    @classmethod
    def encode_thumbnail(self, fpath: str, params: Dict):
        """Return a thumbnail for the video"""
        loaded = cv2.VideoCapture(fpath)
        ret, frame = loaded.read()
        if not ret:
            raise VideoReadException(f"Failed to read frame from {fpath}")

        THUMBNAIL_FORMAT = ".webp"
        img_bytes = cv2.imencode(THUMBNAIL_FORMAT, frame)[1].tobytes()

        img = Image.open(io.BytesIO(img_bytes))
        thumb = ImageOps.fit(img, (THUMBNAIL_WIDTH, THUMBNAIL_HEIGHT))

        data = list(thumb.getdata())
        no_exif = Image.new(thumb.mode, thumb.size)
        no_exif.putdata(data)

        with io.BytesIO() as output:
            # return the image hash and contents

            no_exif.save(output, **params)
            contents = output.getvalue()

            return PhotoContent(contents)
