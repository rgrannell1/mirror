
from dataclasses import dataclass
import io
import os
import xattr
import hashlib
import warnings
from datetime import datetime
from src.tags import Tags
from src.media import Media

from typing import List, Iterator, Dict, Optional
from PIL import Image, ImageOps, ExifTags

from .constants import (
  ATTR_TAG,
  ATTR_DESCRIPTION,
  EXIF_ATTR_ASSOCIATIONS,
  SET_ATTR_ALBUM,
  THUMBNAIL_WIDTH,
  THUMBNAIL_HEIGHT,
  TITLE_PATTERN,
  DATE_FORMAT
)

from .tagfile import Tagfile
from .album import Album


@dataclass
class TagfileAlbumConfiguration:
  """Tagfile information about an album"""
  fpath: str
  attrs: Dict


@dataclass
class TagfileImageConfiguration:
  """Tagfile information about an image"""
  fpath: str
  album: TagfileAlbumConfiguration
  attrs: Dict


@dataclass
class ImageContent:
  """A dataclass representing an images content"""
  hash: str
  content: str


class PhotoVault:
  """A directory of photos"""
  def __init__(self, path: str, metadata_path: str):
    self.path = path
    self.metadata_path = metadata_path

  def list_images(self) -> List['Photo']:
    """Recursively list all files under a given path.
    """
    images = []

    for dirpath, _, filenames in os.walk(self.path):
      for filename in filenames:
        image_path = os.path.join(dirpath, filename)

        if Photo.is_image(image_path):
          images.append(Photo(image_path, self.metadata_path))

    return images

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
        if filename == 'tags.md':
          yield os.path.join(dirpath, filename)

  def list_tagfile_image(self) -> List[TagfileImageConfiguration]:
    """List images in tagfiles"""

    output = []

    for tagfile in self.list_tagfiles():
      dpath = os.path.dirname(tagfile)

      tag_file = Tagfile.read(tagfile)
      for key, entry in tag_file['images'].items():

        match = TITLE_PATTERN.search(key)
        if match:
            image_name = match.group(1)

        attrs = {}
        for attr in SET_ATTR_ALBUM:
          attrs[attr] = tag_file.get(attr, '')

        output.append(TagfileImageConfiguration(
          fpath=os.path.join(dpath, image_name),
          album=TagfileAlbumConfiguration(
            fpath=dpath,
            attrs=attrs
          ),
          attrs=entry
        ))

    return output

  def list_by_folder(self) -> Dict[str, List['Photo']]:
    """List all images by folder."""

    dirs = {}

    for image in self.list_images():
      dirname = image.dirname()
      if dirname not in dirs:
        dirs[dirname] = []

      dirs[dirname].append(image)

    return dirs

class Photo(Media):
  """A photo, methods for retrieving & setting metadata, and
     methods for encoding images as WEBP."""
  def __init__(self, path: str, metadata_path: str):
    self.path = path
    self.tag_metadata = Tags(metadata_path)

  def get_exif(self) -> Dict:
    """Get EXIF data from a photo."""

    try:
      # ignore image warnings, not all exif will be valid
      with warnings.catch_warnings():
          warnings.filterwarnings("ignore")

          img = Image.open(self.path)
          exif_data = img._getexif()
    except:
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

    date = exif.get('DateTimeOriginal')
    if not date:
      return None

    try:
      return datetime.strptime(date, DATE_FORMAT)
    except:
      return None

  def get_metadata(self) -> Dict:
    """Get metadata from an image as extended-attributes"""

    attrs = {attr for attr in xattr.listxattr(self.path)}

    tags = {}
    if ATTR_TAG in attrs:
      tags = {tag.strip() for tag in xattr.getxattr(self.path, ATTR_TAG).decode('utf-8').split(',')}

    description = ""
    if ATTR_DESCRIPTION in attrs:
      description = xattr.getxattr(self.path, ATTR_DESCRIPTION).decode('utf-8')

    exif_attrs = self.get_exif_metadata()

    return {
      ATTR_TAG: tags,
      ATTR_DESCRIPTION: description,
      **exif_attrs
    }

  def get_description(self) -> Optional[str]:
    """Get the description of an image"""

    return self.get_exif_attr(ATTR_DESCRIPTION, "")

  def get_exif_metadata(self) -> Dict:
    """Get metadata from an image as EXIF data"""
    data = {}

    exif = self.get_exif()

    for attr, exif_key in EXIF_ATTR_ASSOCIATIONS:
      data[attr] = str(exif.get(exif_key, 'Unknown'))

    return data

  def set_metadata(self, attrs, album: TagfileAlbumConfiguration):
    """Set metadata on an image as extended-attributes"""

    Album(album.fpath).set_metadata(album.attrs)

    exif_attrs = self.get_exif_metadata()

    for attr, value in exif_attrs.items():
      self.set_xattr_attr(attr, value)

    for attr, value in attrs.items():
      try:
        if attr == ATTR_TAG:
          self.set_xattr_attr(attr, ', '.join(value))
        else:
          self.set_xattr_attr(attr, value)
      except Exception as err:
        raise ValueError(f"failed to set {attr} to {value} on image") from err

  def published(self) -> bool:
    """Is this image publishable?"""

    md = self.get_metadata()

    tags = md.get(ATTR_TAG, set())
    return 'Published' in tags

  def tag_string(self) -> str:
    """Get the tag csv for an image"""

    return ', '.join(self.tags())

  def tags(self) -> List[str]:
    """Get the tag csv for an image"""

    md = self.get_metadata()

    tags = md.get(ATTR_TAG, set())
    return [tag for tag in self.tag_metadata.expand(tags) if tag]

  def encode_thumbnail(self) -> ImageContent:
    """Encode a image as a thumbnail Webp, and remove EXIF data"""

    img = Image.open(self.path)
    img = img.convert('RGB')

    # reduce the dimensions of the image to the thumbnail size
    thumb = ImageOps.fit(img, (THUMBNAIL_WIDTH, THUMBNAIL_HEIGHT))

    # remove EXIF data from the image by cloning
    data = list(thumb.getdata())
    no_exif = Image.new(thumb.mode, thumb.size)
    no_exif.putdata(data)

    with io.BytesIO() as output:
      # return the image hash and contents

      no_exif.save(output, format="WEBP", lossless=True)
      contents = output.getvalue()

      hasher = hashlib.new('sha256')
      hasher.update(contents)

      return ImageContent(
        hash=hasher.hexdigest(),
        content=contents
      )

  def encode_image(self) -> ImageContent:
    """Encode an image as Webp, and remove EXIF data"""

    img = Image.open(self.path)
    img = img.convert('RGB')

    # remove EXIF data from the image by cloning
    data = list(img.getdata())
    no_exif = Image.new(img.mode, img.size)
    no_exif.putdata(data)

    with io.BytesIO() as output:
      # return the image hash and contents

      no_exif.save(output, format="WEBP", lossless=True)
      contents = output.getvalue()

      hasher = hashlib.new('sha256')
      hasher.update(contents)

      return ImageContent(
        hash=hasher.hexdigest(),
        content=contents
      )
