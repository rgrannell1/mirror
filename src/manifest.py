
import os

import json
import sqlite3

from .constants import TITLE_PATTERN
from .photo import Photo

IMAGES_TABLE = """
create table if not exists images (
  fpath            text primary key,
  tags             text,
  published        boolean,
  image_url        text,
  thumbnail_url    text,
  album            text
)
"""

ALBUM_TABLE = """
create table if not exists albums (
  name             text primary key,
  cover_image      text
)
"""

class Manifest:
  def __init__(self):
    fpath = os.path.expanduser('~/.mirror-manifest.db')
    self.conn = sqlite3.connect(fpath)

  def create(self):
    cursor = self.conn.cursor()

    for table in {IMAGES_TABLE, ALBUM_TABLE}:
      cursor.execute(table)

  def list_publishable(self):
    cursor = self.conn.cursor()
    cursor.execute("select fpath from images where published = '1'")

    for row in cursor.fetchall():
      yield Photo(row[0])

  def add(self, image):
    path = image.path

    published = image.published()
    tag_string = image.tag_string()

    cursor = self.conn.cursor()
    cursor.execute(
      "insert or replace into images (fpath, tags, published) values (?, ?, ?)",
      (path, tag_string, published)
    )
    self.conn.commit()

  def has_thumbnail(self, image):
    cursor = self.conn.cursor()
    cursor.execute("select thumbnail_url from images where fpath = ?", (image.path, ))

    row = cursor.fetchone()

    if not row:
      False

    if row[0]:
      return True
    else:
      return False

  def has_image(self, image):
    cursor = self.conn.cursor()
    cursor.execute("select image_url from images where fpath = ?", (image.path, ))

    row = cursor.fetchone()

    if not row:
      False

    if row[0]:
      return True
    else:
      return False

  def register_thumbnail_url(self, image, url):
    cursor = self.conn.cursor()
    cursor.execute("update images set thumbnail_url = ? where fpath = ?", (url, image.path))
    self.conn.commit()

  def register_image_url(self, image, url):
    cursor = self.conn.cursor()
    cursor.execute("update images set image_url = ? where fpath = ?", (url, image.path))
    self.conn.commit()

  def create_metadata_file(self, manifest_file: str) -> None:
    """Create a metadata file from the stored manifest file."""

    cursor = self.conn.cursor()
    cursor.execute("select fpath,tags,image_url,thumbnail_url from images where published = 'True'")

    folders = {}

    for row in cursor.fetchall():
      fpath, tags, image_url, thumbnail_url = row

      dirname = os.path.dirname(fpath)
      if not dirname in folders:
        folders[dirname] = {
          'name': 'not yet defined',
          'cover_image': 'not yet defined',
          'images': []
        }

      folders[dirname]['images'].append({
        'fpath': fpath,
        'tags': tags.split(', '),
        'image_url': image_url,
        'thumbnail_url': thumbnail_url
      })

    with open(manifest_file, 'w') as conn:
      conn.write(json.dumps(folders))

  def close(self):
    self.conn.close()
