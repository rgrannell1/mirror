
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

  def update(self, image):
    path = image.path
    md = image.get_metadata()

    tags = md.get(ATTR_TAG, set())
    published = 'True' if 'Published' in tags else 'False'
    tag_string =", ".join(tags)

    thumbnail_url, image_url = self.image_urls(path)

    if not thumbnail_url:
      encoded = image.encode_thumbnail()

    if not image_url:
      encoded = image.encode()

    exit(0)

    cursor = self.conn.cursor()
    cursor.execute(
      "insert or replace into images (fpath, tags, published) values (?, ?, ?)",
      (path, tag_string, published)
    )
    self.conn.commit()

  def close(self):
    self.conn.close()
