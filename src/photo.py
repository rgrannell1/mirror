
import re
import io
import os
import xattr
import hashlib

from PIL import Image, ImageOps

from .constants import (
  ATTR_TAG,
  ATTR_ALBUM_TITLE,
  ATTR_ALBUM_COVER,
  THUMBNAIL_WIDTH,
  THUMBNAIL_HEIGHT,
  TITLE_PATTERN
)
from .tags import Tagfile

class PhotoDirectory:
  """A directory of photos"""
  def __init__(self, path):
    self.path = path

  def list_images(self):
    """Recursively list all files under a given path.
    """
    images = []

    for dirpath, _, filenames in os.walk(self.path):
      for filename in filenames:
        image_path = os.path.join(dirpath, filename)

        if Photo.is_image(image_path):
          images.append(Photo(image_path))

    return images

  def list_albums(self):
    """Recursively list all directories under a given path.
    """
    albums = []

    for dirpath, _, _ in os.walk(self.path):
      album = Album(dirpath)
      albums.append(album)

    return albums

  def list_tagfiles(self):
    """List tagfiles across all photo-directories
    """

    for dirpath, _, filenames in os.walk(self.path):
      for filename in filenames:
        if filename == 'tags.md':
          fpath = os.path.join(dirpath, filename)

          tag_file = Tagfile.read(fpath)
          for key, entry in tag_file['images'].items():

            match = TITLE_PATTERN.search(key)
            if match:
                image_name = match.group(1)

            yield {
              "fpath": os.path.join(dirpath, image_name),
              "album": {
                "fpath": dirpath,
                "title": tag_file[ATTR_ALBUM_TITLE],
                "cover": tag_file[ATTR_ALBUM_COVER]
              },
              "attrs": entry
            }

  def list_by_folder(self):
    """List all images by folder.
    """
    dirs = {}

    for image in self.list_images():
      dirname = image.dirname()
      if dirname not in dirs:
        dirs[dirname] = []

      dirs[dirname].append(image)

    return dirs

class Album:
  def __init__(self, path):
    self.path = path

  def get_metadata(self):
    """Get metadata from an image as extended-attributes"""

    attrs = {attr.decode('utf-8') for attr in xattr.listxattr(self.path)}

    if ATTR_ALBUM_TITLE not in attrs:
      return None

    return {
      'fpath': self.path,
      'title': xattr.getxattr(self.path, ATTR_ALBUM_TITLE).decode('utf-8'),
      'cover': xattr.getxattr(self.path, ATTR_ALBUM_COVER).decode('utf-8')
    }

class Photo:
  """A photo, methods for retrieving & setting metadata, and
     methods for encoding images as Webp."""
  def __init__(self, path):
    self.path = path

  @classmethod
  def is_image(cls, path):
    """Check if a given file path is an image.
    """
    image_extensions = ('.jpg', '.jpeg', '.png', '.JPG', '.JPEG', '.PNG')
    return os.path.isfile(path) and path.endswith(image_extensions)

  def name(self):
    """Get the basename of the photo.
    """
    return os.path.basename(self.path)

  def dirname(self):
    """Get the directory name of the photo.
    """
    return os.path.dirname(self.path)

  def get_metadata(self):
    """Get metadata from an image as extended-attributes"""
    attrs = {attr.decode('utf-8') for attr in xattr.listxattr(self.path)}

    if not ATTR_TAG in attrs:
      return {}

    tags = {tag.strip() for tag in xattr.getxattr(self.path, ATTR_TAG).decode('utf-8').split(',')}

    return {
      ATTR_TAG: tags
    }

  def published(self):
    md = self.get_metadata()

    tags = md.get(ATTR_TAG, set())
    return 'Published' in tags

  def tag_string(self):
    md = self.get_metadata()

    tags = md.get(ATTR_TAG, set())
    return ', '.join(tags)

  def set_metadata(self, attrs, album, tag_metadata):
    """Set metadata on an image as extended-attributes"""

    xattr.setxattr(album['fpath'], ATTR_ALBUM_TITLE, album['title'])
    xattr.setxattr(album['fpath'], ATTR_ALBUM_COVER, album['cover'])

    for attr, value in attrs.items():
      if attr != ATTR_TAG:
        xattr.setxattr(self.path, attr, value)
        continue

      tag_set = set()

      for tag in value:
        tag_set.add(tag)

        for new_tag in tag_metadata.add_tags(tag):
          tag_set.add(new_tag)

      xattr.setxattr(self.path, attr, ', '.join(tag_set))

  def encode_thumbnail(self):
    """Encode a image as a thumbnail Webp, and remove EXIF data"""

    img = Image.open(self.path)
    img = img.convert('RGB')
    thumb = ImageOps.fit(img, (THUMBNAIL_WIDTH, THUMBNAIL_HEIGHT))

    data = list(thumb.getdata())
    no_exif = Image.new(thumb.mode, thumb.size)
    no_exif.putdata(data)

    with io.BytesIO() as output:
      no_exif.save(output, format="WEBP", lossless=True)
      contents = output.getvalue()

      hasher = hashlib.new('sha256')
      hasher.update(contents)

      return {
        'hash': hasher.hexdigest(),
        'content': contents
      }


  def encode_image(self):
    """Encode an image as Webp, and remove EXIF data"""

    img = Image.open(self.path)
    img = img.convert('RGB')

    data = list(img.getdata())
    no_exif = Image.new(img.mode, img.size)
    no_exif.putdata(data)

    with io.BytesIO() as output:
      no_exif.save(output, format="WEBP", lossless=True)
      contents = output.getvalue()

      hasher = hashlib.new('sha256')
      hasher.update(contents)

      return {
        'hash': hasher.hexdigest(),
        'content': contents
      }
