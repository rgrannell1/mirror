
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
  fpath            text primary key,
  album_name       text,
  cover_image      text
)
"""

class Manifest:
  def __init__(self):
    fpath = os.path.expanduser('~/.mirror-manifest.db')
    self.conn = sqlite3.connect(fpath)

  def create(self):
    """Create the local database"""

    cursor = self.conn.cursor()

    for table in {IMAGES_TABLE, ALBUM_TABLE}:
      cursor.execute(table)

  def list_publishable(self):
    """List all images that are ready to be published"""

    cursor = self.conn.cursor()
    cursor.execute("select fpath from images where published = '1'")

    for row in cursor.fetchall():
      yield Photo(row[0])

  def add_image(self, image):
    """Add an image to the local database"""

    path = image.path
    album = os.path.dirname(path)

    published = image.published()
    tag_string = image.tag_string()

    cursor = self.conn.cursor()
    cursor.execute(
      """
      insert into images (fpath, tags, published, album)
          values (?, ?, ?, ?)
          on conflict(fpath)
          do update set
              tags = ?,
              published = ?,
              album = ?;
      """,
      (path, tag_string, published, album, tag_string, published, album)
    )
    self.conn.commit()

  def add_album(self, album):
    """Add an album to the local database"""

    fpath = album['fpath']
    album_name = album['title']
    cover_image = album['cover']

    cursor = self.conn.cursor()
    cursor.execute("insert or replace into albums (fpath, album_name, cover_image) values (?, ?, ?)", (
      fpath, album_name, cover_image
    ))
    self.conn.commit()

  def has_thumbnail(self, image):
    """Check if a thumbnail exists, according to the local database"""

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
    """Check if an image exists, according to the local database"""
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
    """Register a thumbnail URL for an image in the local database"""

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
    cursor.execute("""
      select images.fpath, images.tags, images.image_url, images.thumbnail_url, albums.album_name, albums.cover_image
        from images
        inner join albums on images.album = albums.fpath
        where published = '1'
      """)

    folders = {}

    for row in cursor.fetchall():
      fpath, tags, image_url, thumbnail_url, album_name, cover_image = row

      dirname = os.path.dirname(fpath)
      if not dirname in folders:
        folders[dirname] = {
          'name': album_name,
          'id': dirname,
          'cover_image': os.path.join(dirname, cover_image),
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
    """Close the local database connection"""

    self.conn.close()
