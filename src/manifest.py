from dataclasses import dataclass
import os

import json
import sqlite3
from typing import Iterator, List

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

  TABLES = {IMAGES_TABLE, ALBUM_TABLE, ENCODED_IMAGE_TABLE}

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

  def image_metadata(self, fpath: str) -> ImageMetadata:
    """Get metadata for a specific image"""

    cursor = self.conn.cursor()
    cursor.execute("""
    select
      full_sized_images.url as image_url_jpeg,
      thumbnail_images.url as thumbnail_url_jpeg
      images.date_time as date_time,
      albums.album_name as album_name,
    from images
    inner join albums on images.album = albums.fpath
    inner join encoded_images as full_sized_images
      on full_sized_images .fpath = images.fpath
    inner join encoded_images as thumbnail_images
      on thumbnail_images.fpath = images.fpath
    where images.published = '1'
      and images.fpath = ?
      and (
        (full_sized_images.mimetype = 'image/jpeg' and full_sized_images.role = 'thumbnail_lossy')
        or
        (thumbnail_images.mimetype = 'image/jpeg' and thumbnail_images.role = 'full_image_lossy'))
    """, (fpath, ))

    row = cursor.fetchone()

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
        "width": exif_md[ATTR_WIDTH],
        "height": exif_md[ATTR_HEIGHT],
    }

    cursor = self.conn.cursor()
    cursor.execute(
        """
        insert into images (fpath, tags, published, album, description, date_time, f_number, focal_length, model, iso, blur, width, height)
        values (:fpath, :tags, :published, :album, :description, :date_time, :f_number, :focal_length, :model, :iso, :blur, :width, :height)
        on conflict(fpath)
        do update set
            tags =         :tags,
            published =    :published,
            album =        :album,
            description =  :description,
            date_time =    :date_time,
            f_number =     :f_number,
            focal_length = :focal_length,
            model =        :model,
            iso =          :iso,
            blur =         :blur,
            width =        :width,
            height =       :height
        """, params)

    self.conn.commit()

  def add_album(self, album_md: AlbumMetadata):
    """Add an album to the local database"""

    cover_path = os.path.join(album_md.fpath, album_md.cover) if album_md.cover != 'Cover' else None

    cursor = self.conn.cursor()
    cursor.execute(
        "insert or replace into albums (fpath, album_name, cover_image, cover_path, description, geolocation) values (?, ?, ?, ?, ?, ?)",
        (album_md.fpath, album_md.title, album_md.cover, cover_path, album_md.description,
         album_md.geolocation))
    self.conn.commit()

  def has_encoded_image(self, image: Photo, role: str, format='webp'):
    """Check if a thumbnail exists, according to the local database"""

    mimetype = f'image/{format}'

    cursor = self.conn.cursor()
    cursor.execute("""
    select fpath from encoded_images
      where fpath = ? and mimetype = ? and role = ?
    """, (image.path, mimetype, role))

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

  def create_metadata_file(self,
                           manifest_file: str,
                           images: bool = True) -> None:
    """Create a metadata file from the stored manifest file"""

    cursor = self.conn.cursor()
    cursor.execute("""
    select
        images.fpath,
        images.tags,
        ei_image.url as image_url,
        ei_thumbnail.url as thumbnail_url,
        ei_mosaic_thumbnail.url as thumbnail_data_url,
        images.description as photo_description,
        images.date_time,
        images.f_number,
        images.focal_length,
        images.model,
        images.iso,
        images.blur,
        images.width,
        images.height,
        albums.album_name,
        albums.cover_image,
        albums.description,
        albums.min_date,
        albums.max_date,
        albums.geolocation
    from images
    inner join albums on images.album = albums.fpath
    left join encoded_images ei_image on images.fpath = ei_image.fpath
        and ei_image.mimetype = 'image/webp'
        and ei_image.role = 'full_image_lossless'
    left join encoded_images ei_thumbnail on images.fpath = ei_thumbnail.fpath
        and ei_thumbnail.mimetype = 'image/webp'
        and ei_thumbnail.role = 'thumbnail_lossless'
    left join encoded_images ei_mosaic_thumbnail on images.fpath = ei_mosaic_thumbnail.fpath
        and ei_mosaic_thumbnail.mimetype = 'image/bmp'
        and ei_mosaic_thumbnail.role = 'thumbnail_mosaic'
    where images.published = '1';
      """)

    folders = {}

    for row in cursor.fetchall():
      (fpath, tags, image_url, thumbnail_url, thumbnail_data_url, photo_description, date_time,
       f_number, focal_length, model, iso, blur, width, height, album_name,
       cover_image, description, min_date, max_date, geolocation) = row

      dirname = os.path.dirname(fpath)
      album_id = str(hash(dirname))

      if album_id not in folders:
        # construct the album object
        folders[album_id] = {
            'name': album_name,
            'id': album_id,
            'min_date': min_date,
            'max_date': max_date,
            'cover_image': cover_image,
            'description': description,
            'geolocation': geolocation,
            'images': [],
            'image_count': 0
        }

      folders[album_id]['image_count'] += 1

      if images:
        # append each image

        folders[album_id]['images'].append({
            'fpath':
            fpath,
            'id':
            str(hash(fpath)),
            'tags':
            tags.split(', '),
            'description':
            photo_description,
            'exif': {
                'date_time': date_time,
                'f_number': f_number,
                'focal_length': focal_length,
                'model': model,
                'iso': iso,
                'blur': blur,
                'width': width,
                'height': height,
            },
            'image_url':
            image_url.replace(SPACES_DOMAIN, ''),
            'thumbnail_url':
            thumbnail_url.replace(SPACES_DOMAIN, ''),
            'thumbnail_data_url': thumbnail_data_url
        })

    manifest = {'domain': SPACES_DOMAIN, 'folders': folders}

    with open(manifest_file, 'w') as conn:
      conn.write(json.dumps(manifest))

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
