"""Encode video and images"""

import contextlib
import io
import os
from typing import Dict, Optional, Tuple

import cv2
import ffmpeg
from PIL import Image, ImageOps

from mirror.commons.constants import (
    THUMBNAIL_HEIGHT,
    THUMBNAIL_WIDTH,
    VIDEO_THUMBNAIL_FORMAT,
)
from mirror.commons.exceptions import (
    InvalidVideoDimensionsError,
    VideoReadError,
    VideoResolutionLookupError,
)
from mirror.models.photo import PhotoContent


class PhotoEncoder:
    @classmethod
    def compute_contrasting_grey(cls, fpath: str) -> str:
        """
        Uses the LAB colour space (https://en.wikipedia.org/wiki/CIELAB_color_space) to sample
        the lightness of the top-right corner of the image (where the metadata icon sits), then
        picks a grey at least 110 L-units (~43 L*) away to guarantee visible contrast.

        Threshold is the true midpoint (128): dark regions get a lighter grey, light regions
        get a darker grey.
        """

        lab = Image.open(fpath).convert("RGB").convert("LAB")
        lightness_band, _, __ = lab.split()

        width, height = lightness_band.size
        top_right = lightness_band.crop((7 * width // 8, 0, width, height // 8))

        pixels = list(top_right.getdata())
        avg_lightness = sum(pixels) / len(pixels)  # 0-255, proportional to L*

        # Use true midpoint as threshold; always push at least 110 units away
        # to guarantee ~43 L* units of perceptual separation.
        # The old 80% threshold + 60% delta could produce only ~20 L* units
        # of separation for mid-bright images (e.g. avg=200 → target=255, delta=55).
        contrast_delta = 110
        if avg_lightness <= 128:
            target_lightness = min(255, int(avg_lightness) + contrast_delta)
        else:
            target_lightness = max(0, int(avg_lightness) - contrast_delta)

        # Build a neutral Lab colour with that L (a=128, b=128 is neutral axis)
        lightness_img = Image.new("L", (1, 1), int(target_lightness))
        a_img = Image.new("L", (1, 1), 128)
        b_img = Image.new("L", (1, 1), 128)

        rgb_pixel = Image.merge("LAB", (lightness_img, a_img, b_img)).convert("RGB").getpixel((0, 0))

        # averaging channels to get a grey
        grey = int(round(sum(rgb_pixel) / 3))

        return f"#{grey:02X}{grey:02X}{grey:02X}"

    @classmethod
    def encode_image_colours(cls, fpath: str, width: int, height: int) -> list[str]:
        """Create a list of colours in the image, to use as a data-url while the main image loads"""

        with Image.open(fpath) as img:
            rgb = img.convert("RGB")

            # resize directly to mosaic dimensions preserving aspect ratio via fit,
            # so the mosaic represents the actual framing of the image
            smaller = ImageOps.fit(rgb, (width, height), method=Image.Resampling.BILINEAR)

            # getdata() returns pixels in row-major order (left-to-right, top-to-bottom),
            # which matches the frontend's row * cols + col placement
            return [f"#{r:02X}{g:02X}{b:02X}" for r, g, b in smaller.getdata()]

    @classmethod
    def encode(cls, fpath: str, role: str, params: Dict) -> PhotoContent:
        """Encode an image as Webp, optionally resizing, and remove EXIF data"""

        with Image.open(fpath) as img:
            # Optionally resize if width and height are in params
            width = params.get("width")
            height = params.get("height")

            if width and height:
                img = ImageOps.fit(img, (width, height))
            else:
                if role == "thumbnail_lossy":
                    raise ValueError("thumbnail_lossy role requires width and height")

            img.getexif().clear()
            img.info.pop("exif", None)
            img.info.pop("xmp", None)
            img.info.pop("icc_profile", None)

            with io.BytesIO() as output:
                # Remove width and height from params to avoid side-effects
                save_params = {key: val for key, val in params.items() if key not in ("width", "height")}
                img.save(output, **save_params)
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
            raise InvalidVideoDimensionsError(f"Video {fpath} is too small to encode")

        video_codec = "libx264"

        input_args: Dict = {}
        kwargs = {
            "vcodec": video_codec,
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
        with contextlib.suppress(FileNotFoundError):
            os.remove(output_fpath)

        (ffmpeg.input(fpath, **input_args).output(output_fpath, **kwargs).run())

        return output_fpath

    @classmethod
    def resolution(cls, fpath: str) -> Tuple[int, int]:
        """Encode a video"""
        "Returns resolution of the video, if it's possible to determine?"

        probe = ffmpeg.probe(fpath)
        video_streams = [stream for stream in probe["streams"] if stream["codec_type"] == "video"]

        if video_streams:
            width = int(video_streams[0]["width"])
            height = int(video_streams[0]["height"])

            return width, height

        raise VideoResolutionLookupError(f"Failed to determine resolution of {fpath}")

    @classmethod
    def encode_thumbnail(cls, fpath: str, params: Dict, width=THUMBNAIL_WIDTH, height=THUMBNAIL_HEIGHT) -> PhotoContent:
        """Return a thumbnail for the video"""
        loaded = cv2.VideoCapture(fpath)
        try:
            ret, frame = loaded.read()
            if not ret:
                raise VideoReadError(f"Failed to read frame from {fpath}")

            img_bytes = cv2.imencode(VIDEO_THUMBNAIL_FORMAT, frame)[1].tobytes()

            with Image.open(io.BytesIO(img_bytes)) as img:
                thumb = ImageOps.fit(img, (width, height))

                data = list(thumb.getdata())
                no_exif = Image.new(thumb.mode, thumb.size)
                no_exif.putdata(data)

                with io.BytesIO() as output:
                    # return the image hash and contents

                    no_exif.save(output, **params)
                    contents = output.getvalue()

                    return PhotoContent(contents)
        finally:
            loaded.release()
