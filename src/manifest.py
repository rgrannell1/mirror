from dataclasses import dataclass
import os

import json
import sqlite3
from typing import Iterator, List, Optional

from src.album import AlbumMetadata
from .photo import Photo
from .constants import (ATTR_DATE_TIME, ATTR_FSTOP, ATTR_FOCAL_EQUIVALENT,
                        ATTR_MODEL, ATTR_ISO, ATTR_WIDTH, ATTR_HEIGHT,
                        SPACES_DOMAIN)

ENCODED_IMAGE_TABLE = """
create table if not exists encoded_images (
  fpath    text not null,
  mimetype text not null,
  role     text not null,
  url      text not null,

  primary key (fpath, mimetype, role)
)
"""

IMAGES_TABLE = """
create table if not exists images (
  fpath              text primary key,
  tags               text,
  published          boolean,
  description        text,
  album              text,
  date_time          text,
  f_number           text,
  focal_length       text,
  model              text,
  iso                text,
  shutter_speed      text,
  blur               text,
  width              text,
  height             text,
  latitude           text,
  longitude          text,
  address            text,
  foreign key(album) references albums(fpath)
)
"""

ALBUM_TABLE = """
create table if not exists albums (
  fpath            text primary key,
  album_name       text,
  album_path       text,
  cover_image      text,
  description      text,
  min_date         text,
  max_date         text,
  geolocation      text
)
"""

GOOGLE_LABELS_TABLE = """
create table if not exists google_labels (
  fpath          text,
  mid            text,
  description    text,
  score          text,
  topicality     text,

  primary key (fpath, mid)
)
"""

PHOTO_RELATIONS_TABLE = """
create table if not exists photo_relations (
  fpath     text,
  relation  text,
  target    text,

  primary key (fpath, relation, target)
)
"""

@dataclass
class ImageMetadata:
  image_url = str
  thumbnail_url = str
  date_time = str
  album_name = str

  def __init__(self, image_url, thumbnail_url, date_time, album_name):
    self.image_url = image_url
    self.thumbnail_url = thumbnail_url
    self.date_time = date_time
    self.album_name = album_name


class Manifest:
  """The local database containing information about the photo albums"""

  TABLES = {IMAGES_TABLE, ALBUM_TABLE, ENCODED_IMAGE_TABLE, PHOTO_RELATIONS_TABLE, GOOGLE_LABELS_TABLE}

  def __init__(self, db_path: str, metadata_path: str):
    fpath = os.path.expanduser(db_path)
    self.conn = sqlite3.connect(fpath)
    self.metadata_path = metadata_path

  def create(self):
    """Create the local database"""

    cursor = self.conn.cursor()

    for table in Manifest.TABLES:
      cursor.execute(table)

  def list_publishable(self) -> Iterator[Photo]:
    """List all images that are ready to be published"""

    cursor = self.conn.cursor()
    cursor.execute("select fpath from images where published = '1'")

    for row in cursor.fetchall():
      yield Photo(row[0], self.metadata_path)

  def image_metadata(self, fpath: str) -> Optional[ImageMetadata]:
    """Get metadata for a specific image"""

    cursor = self.conn.cursor()
    cursor.execute("""
    select
      full_sized_images.url as image_url_jpeg,
      thumbnail_images.url as thumbnail_url_jpeg,
      images.date_time as date_time,
      albums.album_name as album_name
    from images
    inner join albums on images.album = albums.fpath
    inner join encoded_images as full_sized_images
      on full_sized_images.fpath = images.fpath
    inner join encoded_images as thumbnail_images
      on thumbnail_images.fpath = images.fpath
    where images.published = '1'
      and images.fpath = ?
      and (
        (full_sized_images.mimetype = 'image/webp' and full_sized_images.role = 'full_image_lossless')
        and
        (thumbnail_images.mimetype = 'image/webp' and thumbnail_images.role = 'thumbnail_lossless'))
    """, (fpath, ))


    row = cursor.fetchone()
    if not row:
      return

    return ImageMetadata(image_url=row[0],
                         thumbnail_url=row[1],
                         date_time=row[2],
                         album_name=row[3])

  def add_image(self, image: Photo):
    """Add an image to the local database"""

    path = image.path
    album = os.path.dirname(path)

    exif_md = image.get_exif_metadata()
    params = {
        "fpath": path,
        "tags": image.tag_string(),
        "published": image.published(),
        "album": album,
        "description": image.get_description(),
        "date_time": exif_md[ATTR_DATE_TIME],
        "f_number": exif_md[ATTR_FSTOP],
        "focal_length": exif_md[ATTR_FOCAL_EQUIVALENT],
        "model": exif_md[ATTR_MODEL],
        "iso": exif_md[ATTR_ISO],
        "blur": image.get_blur(),
        "shutter_speed": image.get_shutter_speed(),
        "width": exif_md[ATTR_WIDTH],
        "height": exif_md[ATTR_HEIGHT],
    }

    cursor = self.conn.cursor()
    cursor.execute(
        """
        insert into images (fpath, tags, published, album, description, date_time, f_number, focal_length, model, iso, blur, shutter_speed, width, height)
        values (:fpath, :tags, :published, :album, :description, :date_time, :f_number, :focal_length, :model, :iso, :blur, :shutter_speed, :width, :height)
        on conflict(fpath)
        do update set
            tags =          :tags,
            published =     :published,
            album =         :album,
            description =   :description,
            date_time =     :date_time,
            f_number =      :f_number,
            focal_length =  :focal_length,
            model =         :model,
            iso =           :iso,
            blur =          :blur,
            shutter_speed = :shutter_speed,
            width =         :width,
            height =        :height
        """, params)

    self.conn.commit()

  def has_google_labels(self, fpath: str):
    """Check if Google Vision labels exist for an image"""

    cursor = self.conn.cursor()
    cursor.execute("select fpath from google_labels where fpath = ?", (fpath, ))

    row = cursor.fetchone()

    return row and bool(row[0])

  def add_google_labels(self, fpath: str, labels: List):
    """Add Google Vision labels to the local database"""

    cursor = self.conn.cursor()

    for label in labels:
      cursor.execute("""
      insert or replace into google_labels (fpath, mid, description, score, topicality)
      values (?, ?, ?, ?, ?)
      """, (fpath, label['mid'], label['description'], label['score'], label['topicality']))

    self.conn.commit()

  def add_album(self, album_md: AlbumMetadata):
    """Add an album to the local database"""

    cover_path = os.path.join(album_md.fpath, album_md.cover) if album_md.cover != 'Cover' else None

    cursor = self.conn.cursor()
    cursor.execute(
        "insert or replace into albums (fpath, album_name, cover_image, cover_path, description, geolocation, permalink) values (?, ?, ?, ?, ?, ?, ?)",
        (album_md.fpath, album_md.title, album_md.cover, cover_path, album_md.description,
         album_md.geolocation, album_md.permalink))
    self.conn.commit()

  def clear_photo_relations(self):
    """Clear all relations between images and targets"""

    cursor = self.conn.cursor()
    cursor.execute("delete from photo_relations")
    self.conn.commit

  def add_photo_relation(self, fpath: str, relation: str, target: str):
    """Add a relation between an image and a target"""

    cursor = self.conn.cursor()
    cursor.execute("""
    insert or replace into photo_relations (fpath, relation, target)
    values (?, ?, ?)
    """, (fpath, relation, target))
    self.conn.commit()

  def has_encoded_image(self, image: Photo, role: str):
    """Check if a thumbnail exists, according to the local database"""

    cursor = self.conn.cursor()
    cursor.execute("""
    select fpath from encoded_images
      where fpath = ? and role = ?
    """, (image.path, role))

    row = cursor.fetchone()

    return row and bool(row[0])

  def add_encoded_image_url(self, image: Photo, url: str, role: str, format='webp'):
    """Register a thumbnail URL for an image in the local database"""

    mimetype = f'image/{format}'

    cursor = self.conn.cursor()
    cursor.execute("""
    insert or ignore into encoded_images (fpath, mimetype, role, url)
      values (?, ?, ?, ?)
    """, (image.path, mimetype, role, url))
    self.conn.commit()

  def add_album_dates(self, fpath: str, min_date, max_date):
    """Set minimum and maximum dates for an album"""

    cursor = self.conn.cursor()

    cursor.execute(
        """
      update albums
        set min_date = ?, max_date = ?
      where fpath = ?
    """, (min_date, max_date, fpath))

    self.conn.commit()

  def add_google_photos_metadata(self, fpath: str, address: str, lat: str, lon: str):
    """Insert location data into the images table"""

    cursor = self.conn.cursor()
    cursor.execute("""
    update images
      set latitude = ?, longitude = ?, address = ?
      where fpath like '%' || ?;
    """, (lat, lon, address, fpath))
    self.conn.commit()

  def close(self):
    """Close the local database connection"""

    self.conn.close()
