from functools import lru_cache
import io
import numpy
import os
import cv2
import hashlib
import warnings
from datetime import datetime
from src.tags import Tags
from src.media import Media

from typing import List, Iterator, Dict, Optional
from PIL import Image, ImageOps, ExifTags

from src.types import (
    ImageContent,
    TagfileAlbumConfiguration,
    TagfileImageConfiguration,
    TagfileVideoConfiguration,
)
from src.utils import deterministic_byte_hash
from src.video import Video

from .constants import (
    ATTR_BLUR,
    ATTR_SHUTTER_SPEED,
    ATTR_TAG,
    ATTR_DESCRIPTION,
    EXIF_ATTR_ASSOCIATIONS,
    SET_ATTR_ALBUM,
    THUMBNAIL_WIDTH,
    THUMBNAIL_HEIGHT,
    MOSAIC_WIDTH,
    MOSAIC_HEIGHT,
    TITLE_PATTERN,
    DATE_FORMAT,
)

from .tagfile import Tagfile
from .album import Album


class PhotoVault:
    """A directory of photos"""

    def __init__(self, path: str, metadata_path: str):
        self.path = path
        self.metadata_path = metadata_path

    def list_images(self) -> List["Photo"]:
        """Recursively list all files under a given path."""

        images = []

        for dirpath, _, filenames in os.walk(self.path):
            for filename in filenames:
                image_path = os.path.join(dirpath, filename)

                if not Photo.is_image(image_path):
                    continue

                images.append(Photo(image_path, self.metadata_path))

        return images

    def list_videos(self) -> List["Video"]:
        """Recursively list all files under a given path."""

        videos = []

        for dirpath, _, filenames in os.walk(self.path):
            for filename in filenames:
                video_path = os.path.join(dirpath, filename)

                if not Video.is_video(video_path):
                    continue

                videos.append(Video(video_path, self.metadata_path))

        return videos

    def list_albums(self) -> List[Album]:
        """Recursively list all directories under a given path."""

        albums = []

        for dirpath, _, _ in os.walk(self.path):
            album = Album(dirpath)
            albums.append(album)

        return albums

    def list_tagfiles(self) -> Iterator[str]:
        """List all tagfiles beneath a given path."""

        for dirpath, _, filenames in os.walk(self.path):
            for filename in filenames:
                if filename == "tags.md":
                    yield os.path.join(dirpath, filename)

    def list_tagfile_image(self) -> List[TagfileImageConfiguration]:
        """List images in tagfiles"""

        output = []

        for tagfile in self.list_tagfiles():
            dpath = os.path.dirname(tagfile)

            tag_file = Tagfile.read(tagfile)
            if not tag_file:
                continue

            for key, entry in tag_file["images"].items():
                match = TITLE_PATTERN.search(key)

                if match:
                    image_name = match.group(1)

                attrs = {}
                for attr in SET_ATTR_ALBUM:
                    attrs[attr] = tag_file.get(attr, "")

                output.append(
                    TagfileImageConfiguration(
                        fpath=os.path.join(dpath, image_name),
                        album=TagfileAlbumConfiguration(fpath=dpath, attrs=attrs),
                        attrs=entry,
                    )
                )

        return output

    def list_tagfile_video(self) -> List[TagfileVideoConfiguration]:
        """List videos in tagfiles"""

        video_configs = []

        for tagfile in self.list_tagfiles():
            dpath = os.path.dirname(tagfile)

            tag_file = Tagfile.read(tagfile)

            if not tag_file:
                continue

            for key, entry in tag_file["videos"].items():
                match = TITLE_PATTERN.search(key)

                if match and match.group(1).lower().endswith(".mp4"):
                    video_name = match.group(1)

                album_attrs = {}
                for attr in SET_ATTR_ALBUM:
                    album_attrs[attr] = tag_file.get(attr, "")

                video_configs.append(
                    TagfileVideoConfiguration(
                        fpath=os.path.join(dpath, video_name),
                        album=TagfileAlbumConfiguration(fpath=dpath, attrs=album_attrs),
                        attrs=entry,
                    )
                )
        return video_configs

    def list_by_folder(self) -> Dict[str, Dict]:
        """List all images by folder"""

        dirs: Dict[str, Dict] = {}

        for image in self.list_images():
            dirname = image.dirname()
            if dirname not in dirs:
                dirs[dirname] = {"images": [], "videos": []}

            dirs[dirname]["images"].append(image)

        for video in self.list_videos():
            dirname = video.dirname()
            if dirname not in dirs:
                dirs[dirname] = {"images": [], "videos": []}

            dirs[dirname]["videos"].append(video)

        return dirs


class Photo(Media):
    """A photo, methods for retrieving & setting metadata, and
    methods for encoding images as WEBP."""

    def __init__(self, path: str, metadata_path: str):
        self.path = path
        self.tag_metadata = Tags(metadata_path)

    @lru_cache(maxsize=None)
    def blur_estimate(self) -> float:
        """Compute the variance of the Laplacian of the image to measure sharpness."""

        img = Image.open(self.path).convert("L")
        img_cv = cv2.cvtColor(numpy.array(img), cv2.COLOR_GRAY2BGR)

        return float(cv2.Laplacian(img_cv, cv2.CV_64F).var())

    @lru_cache(maxsize=None)
    def get_exif(self) -> Dict[str, str]:
        """Get EXIF data from a photo."""

        try:
            # ignore image warnings, not all exif will be valid
            with warnings.catch_warnings():
                warnings.filterwarnings("ignore")

                img = Image.open(self.path)
                exif_data = img._getexif()
        except BaseException:
            return {}

        if not exif_data:
            return {}

        output_exif = {}

        for key, val in exif_data.items():
            if key in ExifTags.TAGS:
                output_exif[ExifTags.TAGS[key]] = val
            else:
                output_exif[key] = val

        return output_exif

    def get_created_date(self) -> Optional[datetime]:
        """Get the date an image was created on"""

        exif = self.get_exif()

        date = exif.get("DateTimeOriginal")
        if not date:
            return None

        try:
            return datetime.strptime(date, DATE_FORMAT)
        except BaseException:
            return None

    @lru_cache(maxsize=None)
    def get_blur(self) -> float:
        """Get the blur of an image"""

        existing = self.get_xattr_attr(ATTR_BLUR, None)

        try:
            return round(float(existing)) if existing else round(self.blur_estimate())
        except BaseException:
            return -1

    def get_shutter_speed(self) -> Optional[str]:
        """Get the shutter speed of an image"""

        return self.get_xattr_attr(ATTR_SHUTTER_SPEED, None)

    def get_metadata(self) -> Dict:
        """Get metadata from an image as extended-attributes"""

        exif_attrs = self.get_exif_metadata()

        return {
            ATTR_TAG: self.get_xattr_tags(),
            ATTR_BLUR: self.get_blur(),
            ATTR_DESCRIPTION: self.get_xattr_description(),
            **exif_attrs,
        }

    def get_exif_metadata(self) -> Dict:
        """Get metadata from an image as EXIF data"""
        data = {}

        exif = self.get_exif()

        for attr, exif_key in EXIF_ATTR_ASSOCIATIONS:
            data[attr] = str(exif.get(exif_key, "Unknown"))

        return data

    def set_metadata(self, attrs: Dict, album: TagfileAlbumConfiguration) -> None:
        """Set metadata on an image as extended-attributes"""

        Album(album.fpath).set_xattrs(album.attrs)

        exif_attrs = self.get_exif_metadata()

        # set exif-derived attributes on the image
        for attr, value in exif_attrs.items():
            self.set_xattr_attr(attr, value)

        # set each other attribute
        for attr, value in attrs.items():
            if value is None:
                continue

            try:
                if attr == ATTR_TAG:
                    self.set_xattr_attr(attr, ", ".join(value))
                else:
                    self.set_xattr_attr(attr, value)
            except Exception as err:
                raise ValueError(f"failed to set {attr} to {value} on image") from err

    def encode_thumbnail(self, params: Dict) -> ImageContent:
        """Encode a image as a thumbnail, and remove EXIF data"""

        img = Image.open(self.path)
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
            contents = output.getvalue()

            return ImageContent(
                hash=deterministic_byte_hash(contents), content=contents
            )

    def encode_image_mosaic(self):
        img = Image.open(self.path)
        rgb = img.convert("RGB")

        # reduce the dimensions of the image to the thumbnail size
        thumb = ImageOps.fit(rgb, (THUMBNAIL_WIDTH, THUMBNAIL_HEIGHT))

        # remove EXIF data from the image by cloning
        data = list(thumb.getdata())
        no_exif = Image.new(thumb.mode, thumb.size)
        no_exif.putdata(data)

        # resize down to a tiny mosaic data-url that can be used to
        # "progressively render" a photo.
        smaller = no_exif.resize(
            (MOSAIC_WIDTH, MOSAIC_HEIGHT), resample=Image.Resampling.BILINEAR
        )

        with io.BytesIO() as output:
            smaller.save(output, format="bmp", lossless=True)
            contents = output.getvalue()

            hasher = hashlib.new("sha256")
            hasher.update(contents)

            return ImageContent(hash=hasher.hexdigest(), content=contents)

    def encode_image(self, params: Dict) -> ImageContent:
        """Encode an image as Webp, and remove EXIF data"""

        img = Image.open(self.path)
        rgb = img.convert("RGB")

        # remove EXIF data from the image by cloning
        data = list(rgb.getdata())
        no_exif = Image.new(rgb.mode, rgb.size)
        no_exif.putdata(data)

        with io.BytesIO() as output:
            # return the image hash and contents

            no_exif.save(output, **params)
            contents = output.getvalue()

            return ImageContent(
                hash=deterministic_byte_hash(contents), content=contents
            )
