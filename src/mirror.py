"""The core logic of mirror. This is the entrypoint for the CLI, and
   contains the logic for each command."""

import sys
import json

from src.photo import PhotoDirectory, Photo, Album
from src.tags import Tagfile, TagMetadata
from .constants import ATTR_TAG
from .spaces import Spaces
from .manifest import Manifest

def init(dir: str):
  """Create tags.md files in each photo-directory, with information
     extracted from extended-attributes. Create a manifest"""
  for dirname, images in PhotoDirectory(dir).list_by_folder().items():
    continue
    Tagfile(dirname, images).write()

  db = Manifest()
  db.create()

  for image in PhotoDirectory(dir).list_images():
    db.add_image(image)

  for album in PhotoDirectory(dir).list_albums():
    md = album.get_metadata()

    if not md:
      continue

    db.add_album(md)


def tag(dir: str, metadata_path: str):
  """Read tags.md files in each photo-directory, and write extended
     attributes to each image"""

  photo_dir = PhotoDirectory(dir)
  tag_metadata = TagMetadata(metadata_path)

  for entry in photo_dir.list_tagfiles():
    fpath = entry['fpath']
    attrs = entry['attrs']
    album = entry['album']

    Photo(fpath).set_metadata(attrs, album, tag_metadata)

def list_tags(dir: str):
  """List all tags in all images in the directory, as a series
     of JSON objects"""
  tag_set = {}

  for image in PhotoDirectory(dir).list_images():
    tags = image.has_metadata()

    if ATTR_TAG not in tags:
      continue

    for tag in tags[ATTR_TAG]:
      if tag not in tag_set:
        tag_set[tag] = 1

      tag_set[tag] += 1

  for tag, count in tag_set.items():
    print(json.dumps({
      'tag': tag,
      'count': count
    }))

def list_photos(dir: str, tag: str):
  """List all photos in the directory, as a series of JSON objects. If
     a tag is specified, only list photos with that tag"""

  for image in PhotoDirectory(dir).list_images():
    attrs = image.has_metadata()

    if tag and tag not in attrs.get(ATTR_TAG, []):
      continue

    if ATTR_TAG in attrs:
      attrs[ATTR_TAG] = list(attrs[ATTR_TAG])

    print(json.dumps({
      'fpath': image.path,
      'attrs': attrs
    }))

def publish(dir: str):
  """List all images tagged with 'Published'. Find what images are already published,
  and compute a minimal set of optimised Webp images and thumbnails to publish. Publish
  the images to DigitalOcean Spaces.
  """

  db = Manifest()
  db.create()

  spaces = Spaces()
  spaces.set_acl()

  published = False

  for image in db.list_publishable():
    published = True
    print(f'Checking thumbnail for {image.path}', file=sys.stderr)

    # create and upload a thumbnail
    if not db.has_thumbnail(image):
      encoded = image.encode_thumbnail()

      thumbnail_in_spaces, thumbnail_url = spaces.has_thumbnail(encoded)

      if not thumbnail_in_spaces:
        spaces.upload_thumbnail(encoded)
        print(f'Uploaded thumbnail for {image.path}', file=sys.stderr)

      db.register_thumbnail_url(image, thumbnail_url)

    print(f'Checking image for {image.path}', file=sys.stderr)

    # create an upload the image itself
    if not db.has_image(image):
      encoded = image.encode_image()

      image_in_spaces, image_url = spaces.has_image(encoded)

      if not image_in_spaces:
        spaces.upload_image(encoded)
        print(f'Uploaded image for {image.path}', file=sys.stderr)

      db.register_image_url(image, image_url)

  if not published:
    print('No images published', file=sys.stderr)

  for dir, images in PhotoDirectory(dir).list_by_folder().items():
    album = Album(dir)

    try:
      min_date = min(img.get_created_date() for img in images if img.get_created_date())
      max_date = max(img.get_created_date() for img in images if img.get_created_date())
    except ValueError:
      pass

    if not min_date or not max_date:
      continue

    min_timestamp_ms = min_date.timestamp() * 1_000
    max_timestamp_ms = max_date.timestamp() * 1_000

    db.register_dates(album.path, min_timestamp_ms, max_timestamp_ms)

  db.create_metadata_file('/home/rg/Code/photos.rgrannell.xyz/manifest.json')
