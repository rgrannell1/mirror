
import io
import re
import os
import xattr
import hashlib
import warnings
import requests
from datetime import datetime
from src.tags import Tags

from typing import List, Iterator, Dict, Optional
from PIL import Image, ImageOps, ExifTags

from .constants import (
  ATTR_TAG,
  ATTR_DESCRIPTION,
  ATTR_DATE_TIME,
  ATTR_FSTOP,
  ATTR_FOCAL_EQUIVALENT,
  ATTR_MODEL,
  ATTR_ISO,
  ATTR_WIDTH,
  ATTR_HEIGHT,
  ATTR_ALBUM_TITLE,
  ATTR_ALBUM_COVER,
  ATTR_ALBUM_DESCRIPTION,
  THUMBNAIL_WIDTH,
  THUMBNAIL_HEIGHT,
  TITLE_PATTERN,
  ATTR_ALBUM_GEOLOCATION
)

from .tagfile import Tagfile
from .album import Album

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
    """Recursively list all directories under a given path.
    """
    albums = []

    for dirpath, _, _ in os.walk(self.path):
      album = Album(dirpath)
      albums.append(album)

    return albums

  def list_tagfiles(self) -> Iterator[str]:
    for dirpath, _, filenames in os.walk(self.path):
      for filename in filenames:
        if filename == 'tags.md':
          yield os.path.join(dirpath, filename)

  def list_tagfiles_and_archives(self) -> Iterator[Dict]:
    for dirpath, _, filenames in os.walk(self.path):
      for filename in filenames:
        if filename == 'tags.md':
          yield {
            'current': True,
            'dpath': dirpath,
            'fpath': os.path.join(dirpath, filename)
          }

        matches = re.match("tags\.md-[0-9]{4}-[0-9]{1,2}-[0-9]{2}_[0-9]{2}-[0-9]{2}-[0-9]{2}", filename)
        if matches is None:
          continue

        yield {
          'current': False,
          'dpath': dirpath,
          'fpath': os.path.join(dirpath, filename)
        }

  def list_tagfile_image(self) -> Iterator[Dict]:
    """List tagfiles across all photo-directories
    """

    for tagfile in self.list_tagfiles():
      dpath = os.path.dirname(tagfile)

      tag_file = Tagfile.read(tagfile)
      for key, entry in tag_file['images'].items():

        match = TITLE_PATTERN.search(key)
        if match:
            image_name = match.group(1)

        yield {
          "fpath": os.path.join(dpath, image_name),
          "album": {
            "fpath": dpath,
            "attrs": {
              ATTR_ALBUM_TITLE: tag_file.get(ATTR_ALBUM_TITLE, ''),
              ATTR_ALBUM_COVER: tag_file.get(ATTR_ALBUM_COVER, ''),
              ATTR_ALBUM_DESCRIPTION: tag_file.get(ATTR_ALBUM_DESCRIPTION, ''),
              ATTR_ALBUM_GEOLOCATION: tag_file.get(ATTR_ALBUM_GEOLOCATION, '')
            }
          },
          "attrs": entry
        }

  def list_by_folder(self) -> Dict[str, List['Photo']]:
    """List all images by folder.
    """
    dirs = {}

    for image in self.list_images():
      dirname = image.dirname()
      if dirname not in dirs:
        dirs[dirname] = []

      dirs[dirname].append(image)

    return dirs

class Photo:
  """A photo, methods for retrieving & setting metadata, and
     methods for encoding images as Webp."""
  def __init__(self, path: str, metadata_path: str):
    self.path = path
    self.tag_metadata = Tags(metadata_path)

  @classmethod
  def is_image(cls, path) -> bool:
    """Check if a given file path is an image.
    """
    image_extensions = ('.jpg', '.jpeg', '.png', '.JPG', '.JPEG', '.PNG')
    return os.path.isfile(path) and path.endswith(image_extensions)

  def name(self) -> str:
    """Get the basename of the photo.
    """
    return os.path.basename(self.path)

  def dirname(self) -> str:
    """Get the directory name of the photo.
    """
    return os.path.dirname(self.path)

  def exists(self) -> bool:
    """Check if a photo exists.
    """
    return os.path.exists(self.path)

  def get_exif(self) -> Dict:
    """Get EXIF data from a photo."""

    try:
      with warnings.catch_warnings():
          warnings.filterwarnings("ignore")

          img = Image.open(self.path)
          exif_data = img._getexif()
    except:
      return {}

    if not exif_data:
      return {}

    output = {}

    for key, val in exif_data.items():
      if key in ExifTags.TAGS:
        output[ExifTags.TAGS[key]] = val
      else:
        output[key] = val

    return output

  def get_created_date(self) -> Optional[datetime]:
    """Get the date an image was created on"""

    exif = self.get_exif()

    date = exif.get('DateTimeOriginal')
    if not date:
      return None

    date_format = "%Y:%m:%d %H:%M:%S"

    try:
      return datetime.strptime(date, date_format)
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

    attrs = {attr for attr in xattr.listxattr(self.path)}

    if ATTR_DESCRIPTION in attrs:
      return xattr.getxattr(self.path, ATTR_DESCRIPTION).decode('utf-8')

    return ""

  def get_exif_metadata(self) -> Dict:
    """Get metadata from an image as EXIF data"""
    data = {}

    exif = self.get_exif()

    data[ATTR_DATE_TIME] = str(exif.get('DateTimeOriginal', 'Unknown'))
    data[ATTR_FSTOP] = str(exif.get('FNumber', 'Unknown'))
    data[ATTR_FOCAL_EQUIVALENT] = str(exif.get('FocalLengthIn35mmFilm', 'Unknown'))
    data[ATTR_MODEL] = str(exif.get('Model', 'Unknown'))
    data[ATTR_ISO] = str(exif.get('PhotographicSensitivity', 'Unknown'))
    data[ATTR_WIDTH] = str(exif.get('ExifImageWidth', 'Unknown'))
    data[ATTR_HEIGHT] = str(exif.get('ExifImageHeight', 'Unknown'))

    return data

  def set_xattr(self, attr, value):
    """Set an extended-attribute on an image"""
    try:
      xattr.setxattr(self.path, attr.encode(), value.encode())
    except Exception as err:
      raise ValueError(f"failed to set xattr {attr} on {self.path}") from err

  def set_metadata(self, attrs, album):
    """Set metadata on an image as extended-attributes"""

    Album(album['fpath']).set_metadata(album['attrs'])

    exif_attrs = self.get_exif_metadata()
    # location = self.estimate_location()
    location = None

    if location:
      for attr, value in location.items():
        self.set_xattr(attr, value)

    for attr, value in exif_attrs.items():
      self.set_xattr(attr, value)

    for attr, value in attrs.items():
      if attr != ATTR_TAG:
        self.set_xattr(attr, value)
        continue

      self.set_xattr(attr, ', '.join(value))

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

  def encode_thumbnail(self) -> Dict:
    """Encode a image as a thumbnail Webp, and remove EXIF data"""

    img = Image.open(self.path)
    img = img.convert('RGB')

    # reduce the dimensions of the image
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

      return {
        'hash': hasher.hexdigest(),
        'content': contents
      }

  def encode_image(self) -> Dict:
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

      return {
        'hash': hasher.hexdigest(),
        'content': contents
      }
