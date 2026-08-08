"""Encode video and images"""

import base64
import contextlib
import io
import os
from typing import Dict, Optional, Tuple

import cv2
import ffmpeg
from PIL import Image, ImageOps
from thumbhash import rgba_to_thumb_hash

from mirror.commons.constants import (
    CONTRAST_DELTA,
    LIGHTNESS_MIDPOINT,
    THUMBHASH_MAX_DIMENSION,
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


def sample_corner_lightness(fpath: str) -> float:
    """Average lightness (0-255, proportional to L*) of the image's top-right corner."""
    lab = Image.open(fpath).convert("RGB").convert("LAB")
    lightness_band, _, __ = lab.split()

    width, height = lightness_band.size
    top_right = lightness_band.crop((7 * width // 8, 0, width, height // 8))

    pixels = list(top_right.getdata())
    return sum(pixels) / len(pixels)


def contrasting_lightness(avg_lightness: float) -> int:
    """Pick a lightness pushed at least CONTRAST_DELTA away from the sample.

    Use true midpoint as threshold; always push at least 110 units away
    to guarantee ~43 L* units of perceptual separation.
    The old 80% threshold + 60% delta could produce only ~20 L* units
    of separation for mid-bright images (e.g. avg=200 → target=255, delta=55)."""
    if avg_lightness <= LIGHTNESS_MIDPOINT:
        return min(255, int(avg_lightness) + CONTRAST_DELTA)

    return max(0, int(avg_lightness) - CONTRAST_DELTA)


def neutral_grey_hex(target_lightness: int) -> str:
    """Convert a Lab lightness into a neutral grey hex colour."""
    # Build a neutral Lab colour with that L (a=128, b=128 is neutral axis)
    lightness_img = Image.new("L", (1, 1), int(target_lightness))
    a_img = Image.new("L", (1, 1), 128)
    b_img = Image.new("L", (1, 1), 128)

    merged = Image.merge("LAB", (lightness_img, a_img, b_img)).convert("RGB")
    rgb_pixel = merged.getpixel((0, 0))

    # averaging channels to get a grey
    grey = int(round(sum(rgb_pixel) / 3))
    return f"#{grey:02X}{grey:02X}{grey:02X}"


def scrub_image_metadata(img) -> None:
    """Remove EXIF and embedded metadata blocks in-place."""
    img.getexif().clear()
    img.info.pop("exif", None)
    img.info.pop("xmp", None)
    img.info.pop("icc_profile", None)


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

        avg_lightness = sample_corner_lightness(fpath)
        target_lightness = contrasting_lightness(avg_lightness)
        return neutral_grey_hex(target_lightness)

    @classmethod
    def encode_thumbhash(cls, fpath: str) -> str:
        """Encode the image as an unpadded-base64 ThumbHash placeholder string.

        The hash keeps the full frame. The frontend crops it to each display
        shape with object-fit: cover, so a full-frame hash serves every
        rendition at the smallest byte cost.

        The image is flattened to opaque RGBA before hashing. The library's
        alpha path is broken (a tuple-assignment bug), and our photos carry
        no meaningful transparency."""

        with Image.open(fpath) as img:
            oriented = ImageOps.exif_transpose(img)
            rgb = oriented.convert("RGB")
            rgb.thumbnail((THUMBHASH_MAX_DIMENSION, THUMBHASH_MAX_DIMENSION))

            rgba = []
            for red, green, blue in rgb.get_flattened_data():
                rgba.extend((red, green, blue, 255))

            hash_bytes = bytes(rgba_to_thumb_hash(rgb.width, rgb.height, rgba))

        return base64.b64encode(hash_bytes).decode("ascii").rstrip("=")

    @classmethod
    def encode(cls, fpath: str, role: str, params: Dict) -> PhotoContent:
        """Encode an image as Webp, optionally resizing, and remove EXIF data"""

        with Image.open(fpath) as img:
            # Optionally resize if width and height are in params
            width = params.get("width")
            height = params.get("height")

            if width and height:
                img = ImageOps.fit(img, (width, height))
            elif role == "thumbnail_lossy":
                raise ValueError("thumbnail_lossy role requires width and height")

            scrub_image_metadata(img)

            with io.BytesIO() as output:
                # Remove width and height from params to avoid side-effects
                resize_keys = {"width", "height"}
                save_params = {key: val for key, val in params.items() if key not in resize_keys}

                img.save(output, **save_params)
                return PhotoContent(output.getvalue())


def is_undersized(actual_width: Optional[int], actual_height: Optional[int], params: Dict) -> bool:
    """True when the source video is smaller than the requested encode size."""
    width, height = params["width"], params["height"]
    if not (actual_width and actual_height and width and height):
        return False

    return actual_width < width or actual_height < height


def video_encode_args(params: Dict, share_audio: bool) -> tuple[Dict, Dict]:
    """ffmpeg input and output arguments for one video encode."""
    input_args: Dict = {}
    kwargs = {
        "vcodec": "libx264",
        "video_bitrate": params["bitrate"],
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

    if params["width"] and params["height"]:
        kwargs["vf"] = f"scale={params['width']}:{params['height']}"

    return input_args, kwargs


def read_first_frame(fpath: str) -> bytes:
    """First frame of a video, as encoded image bytes."""
    loaded = cv2.VideoCapture(fpath)
    try:
        ret, frame = loaded.read()
        if not ret:
            raise VideoReadError(f"Failed to read frame from {fpath}")

        return cv2.imencode(VIDEO_THUMBNAIL_FORMAT, frame)[1].tobytes()
    finally:
        loaded.release()


class VideoEncoder:
    """Encode & interact with video"""

    @classmethod
    def encode(
        cls, fpath: str, upload_file_name: str, params: Dict, share_audio: bool = False
    ) -> Optional[str]:
        """Encode the video"""

        actual_width, actual_height = cls.resolution(fpath)
        if is_undersized(actual_width, actual_height, params):
            raise InvalidVideoDimensionsError(f"Video {fpath} is too small to encode")

        input_args, kwargs = video_encode_args(params, share_audio)

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
    def encode_thumbnail(
        cls, fpath: str, params: Dict, width=THUMBNAIL_WIDTH, height=THUMBNAIL_HEIGHT
    ) -> PhotoContent:
        """Return a thumbnail for the video"""
        img_bytes = read_first_frame(fpath)

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
