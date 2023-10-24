
import os

import sqlite3

from .constants import ATTR_TAG
from .photo import Photo

IMAGES_TABLE = """
create table if not exists images (
  fpath            text primary key,
  tags             text,
  published        boolean,
  image_url        text,
  thumbnail_url    text
)
"""

class Manifest:
  def __init__(self):
    fpath = os.path.expanduser('~/.mirror-manifest.db')
    self.conn = sqlite3.connect(fpath)

  def create(self):
    cursor = self.conn.cursor()

    for table in {IMAGES_TABLE}:
      cursor.execute(table)

  def list_publishable(self):
    cursor = self.conn.cursor()
    cursor.execute("select fpath from images where published = 'True'")

    for row in cursor.fetchall():
      yield Photo(row[0])

  def image_urls(self, fpath: str):
    cursor = self.conn.cursor()
    cursor.execute("select thumbnail_url, image_url from images where fpath = ?", (fpath, ))

    row = cursor.fetchone()

    if not row:
      return None, None

    return row[0], row[1]

  def add(self, image):
    path = image.path

    published = image.published()
    tag_string = image.tag_string()

    thumbnail_url, image_url = self.image_urls(path)

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

  def close(self):
    self.conn.close()
