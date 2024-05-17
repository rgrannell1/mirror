
import os

import json
import yaml
import sqlite3

from typing import Iterator

from .photo import Photo
from .constants import (
  ATTR_DATE_TIME,
  ATTR_FSTOP,
  ATTR_FOCAL_EQUIVALENT,
  ATTR_MODEL,
  ATTR_ISO,
  ATTR_WIDTH,
  ATTR_HEIGHT,
  ATTR_LOCATION_ADDRESS,
  ATTR_LOCATION_LONGITUDE,
  ATTR_LOCATION_LATITUDE,
  SPACES_DOMAIN
)

IMAGES_TABLE = """
create table if not exists images (
  fpath            text primary key,
  tags             text,
  published        boolean,
  image_url        text,
  thumbnail_url    text,
  description      text,
  album            text,
  dateTime         text,
  fNumber          text,
  focalLength      text,
  model            text,
  iso              text,
  width            text,
  height           text,
  address          text,
  longitude        text,
  latitude         text,
  foreign key(album) references albums(fpath)
)
"""

ALBUM_TABLE = """
create table if not exists albums (
  fpath            text primary key,
  album_name       text,
  cover_image      text,
  description      text,
  min_date         text,
  max_date         text
)
"""

class Manifest:
  def __init__(self, metadata_path: str):
    fpath = os.path.expanduser('/home/rg/.mirror-manifest.db')
    self.conn = sqlite3.connect(fpath)
    self.metadata_path = metadata_path

  def create(self):
    """Create the local database"""

    cursor = self.conn.cursor()

    for table in {IMAGES_TABLE, ALBUM_TABLE}:
      cursor.execute(table)

  def list_publishable(self) -> Iterator[Photo]:
    """List all images that are ready to be published"""

    cursor = self.conn.cursor()
    cursor.execute("select fpath from images where published = '1'")

    for row in cursor.fetchall():
      yield Photo(row[0], self.metadata_path)

  def image_metadata(self, fpath: str) -> Iterator:
    cursor = self.conn.cursor()
    cursor.execute("""select
      images.image_url, images.thumbnail_url,
      images.dateTime, albums.album_name
    from images
    inner join albums on images.album = albums.fpath
    where published = '1' and images.fpath = ?
    """, (fpath,))

    row = cursor.fetchone()
    return row


  def add_image(self, image):
    """Add an image to the local database"""


    path = image.path
    album = os.path.dirname(path)

    published = image.published()
    tag_string = image.tag_string()

    cursor = self.conn.cursor()

    exif_md = image.get_exif_metadata()
    description = image.get_description()

    dateTime = exif_md[ATTR_DATE_TIME]
    fNumber = exif_md[ATTR_FSTOP]
    focalLength = exif_md[ATTR_FOCAL_EQUIVALENT]
    model = exif_md[ATTR_MODEL]
    iso = exif_md[ATTR_ISO]
    width = exif_md[ATTR_WIDTH]
    height = exif_md[ATTR_HEIGHT]

    #data = image.estimate_location()
    data = None

    if not data:
      data = {}

    address = data.get(ATTR_LOCATION_ADDRESS)
    longitude = data.get(ATTR_LOCATION_LONGITUDE)
    latitude = data.get(ATTR_LOCATION_LATITUDE)

    params = {
        "fpath": path,
        "tags": tag_string,
        "published": published,
        "album": album,
        "description": description,
        "dateTime": dateTime,
        "fNumber": fNumber,
        "focalLength": focalLength,
        "model": model,
        "iso": iso,
        "width": width,
        "height": height,
        "address": address,
        "longitude": longitude,
        "latitude": latitude
    }

    cursor.execute(
        """
        insert into images (fpath, tags, published, album, description, dateTime, fNumber, focalLength, model, iso, width, height, address, longitude, latitude)
        values (:fpath, :tags, :published, :album, :description, :dateTime, :fNumber, :focalLength, :model, :iso, :width, :height, :address, :longitude, :latitude)
        on conflict(fpath)
        do update set
            tags = :tags,
            published = :published,
            album = :album,
            description = :description,
            dateTime = :dateTime,
            fNumber = :fNumber,
            focalLength = :focalLength,
            model = :model,
            iso = :iso,
            width = :width,
            height = :height,
            address = :address,
            longitude = :longitude,
            latitude = :latitude;
        """,
        params
    )

    self.conn.commit()

  def add_album(self, album):
    """Add an album to the local database"""

    fpath = album['fpath']
    album_name = album['title']
    cover_image = album['cover']
    description = album['description']

    cursor = self.conn.cursor()
    cursor.execute("insert or replace into albums (fpath, album_name, cover_image, description) values (?, ?, ?, ?)", (
      fpath, album_name, cover_image, description
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

  def register_dates(self, fpath, min_date, max_date):
    cursor = self.conn.cursor()
    cursor.execute("""
    update albums
      set min_date = ?, max_date = ?
    where fpath = ?
    """, (min_date, max_date, fpath))

    self.conn.commit()

  def copy_metadata_file(self, metadata_path: str, manifest_path: str) -> None:
    """Copy the metadata file to the destination"""

    manifest_dname = os.path.dirname(manifest_path)
    metadata_dst = os.path.join(manifest_dname, 'metadata.json')

    content = yaml.safe_load(open(metadata_path))

    with open(metadata_dst, 'w') as conn:
      conn.write(json.dumps(content))

  def create_metadata_file(self, manifest_file: str, images: bool = True) -> None:
    """Create a metadata file from the stored manifest file."""

    cursor = self.conn.cursor()
    cursor.execute("""
      select
          images.fpath, images.tags, images.image_url, images.thumbnail_url, images.description as photo_description,
          images.dateTime, images.fNumber, images.focalLength, images.model,
          images.iso, images.width, images.height,
          images.address, images.longitude, images.latitude,
          albums.album_name, albums.cover_image, albums.description, albums.min_date, albums.max_date
        from images
        inner join albums on images.album = albums.fpath
        where published = '1'
      """)

    folders = {}

    for row in cursor.fetchall():
      (
        fpath, tags, image_url, thumbnail_url, photo_description, dateTime,
        fNumber, focalLength, model, iso, width, height,
        address, longitude, latitude, album_name, cover_image, description, min_date, max_date) = row

      dirname = os.path.dirname(fpath)
      album_id = str(hash(dirname))

      if not album_id in folders:
        folders[album_id] = {
          'name': album_name,
          'id': album_id,
          'min_date': min_date,
          'max_date': max_date,
          'cover_image': os.path.join(dirname, cover_image),
          'description': description,
          'images': [],
          'image_count': 0
        }

      folders[album_id]['image_count'] += 1

      if images:
        folders[album_id]['images'].append({
          'fpath': fpath,
          'id': str(hash(fpath)),
          'tags': tags.split(', '),
          'description': photo_description,
          'exif': {
            'dateTime': dateTime,
            'fNumber': fNumber,
            'focalLength': focalLength,
            'model': model,
            'iso': iso,
            'width': width,
            'height': height,
          },
          #'location': {
          #  'address': address,
          #  'longitude': longitude,
          #  'latitude': latitude
          #},
          'image_url': image_url.replace(SPACES_DOMAIN, ''),
          'thumbnail_url': thumbnail_url.replace(SPACES_DOMAIN, '')
        })

    manifest = {
      'domain': SPACES_DOMAIN,
      'folders': folders
    }

    with open(manifest_file, 'w') as conn:
      conn.write(json.dumps(manifest))

  def close(self):
    """Close the local database connection"""

    self.conn.close()
