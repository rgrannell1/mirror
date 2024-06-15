from dataclasses import dataclass
import os

import json
import yaml
import sqlite3
from typing import Iterator, List
import numpy as np

from src.album import AlbumMetadata
from src.faces import Face
from .photo import Photo
from .constants import (ATTR_DATE_TIME, ATTR_FSTOP, ATTR_FOCAL_EQUIVALENT,
                        ATTR_MODEL, ATTR_ISO, ATTR_WIDTH, ATTR_HEIGHT,
                        SPACES_DOMAIN)

IMAGES_TABLE = """
create table if not exists images (
  fpath              text primary key,
  tags               text,
  published          boolean,
  image_url          text,
  thumbnail_url      text,
  image_url_jpeg     text,
  thumbnail_url_jpeg text,
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
  cover_image      text,
  description      text,
  min_date         text,
  max_date         text,
  geolocation      text
)
"""

IMAGE_FACES_TABLE = """
create table if not exists faces (
  x0                 text,
  y0                 text,
  x1                 text,
  y1                 text,
  identity           text,
  image              text,
  encoding           blob,

  primary key(x0, y0, x1, y1, identity, image)
)
"""

IMAGE_JOBS = """
create table if not exists jobs (
  face_detection     boolean,
  image              text,

  primary key(image)
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

  def __init__(self, db_path: str, metadata_path: str):
    fpath = os.path.expanduser(db_path)
    self.conn = sqlite3.connect(fpath)
    self.metadata_path = metadata_path

  def create(self):
    """Create the local database"""

    cursor = self.conn.cursor()

    for table in {IMAGES_TABLE, ALBUM_TABLE, IMAGE_FACES_TABLE, IMAGE_JOBS}:
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
    cursor.execute(
        """
      select
        images.image_url_jpeg, images.thumbnail_url_jpeg,
        images.date_time, albums.album_name
      from images
      inner join albums on images.album = albums.fpath
      where published = '1' and images.fpath = ?
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

    cursor = self.conn.cursor()
    cursor.execute(
        "insert or replace into albums (fpath, album_name, cover_image, description, geolocation) values (?, ?, ?, ?, ?)",
        (album_md.fpath, album_md.title, album_md.cover, album_md.description,
         album_md.geolocation))
    self.conn.commit()

  def has_thumbnail(self, image: Photo, format='webp'):
    """Check if a thumbnail exists, according to the local database"""

    target_column = 'thumbnail_url'
    if format == 'jpeg':
      target_column = 'thumbnail_url_jpeg'

    cursor = self.conn.cursor()
    cursor.execute(f"select {target_column} from images where fpath = ?",
                   (image.path, ))

    row = cursor.fetchone()

    return row and bool(row[0])

  def has_image(self, image, format='webp'):
    """Check if an image exists, according to the local database"""

    target_column = 'image_url'
    if format == 'jpeg':
      target_column = 'image_url_jpeg'

    cursor = self.conn.cursor()
    cursor.execute(f"select {target_column} from images where fpath = ?",
                   (image.path, ))

    row = cursor.fetchone()

    return row and bool(row[0])

  def list_faces(self, identified=False) -> Iterator:
    """Get faces from the local database"""

    cursor = self.conn.cursor()

    if identified:
      cursor.execute("select image, identity, x0, y0, x1, y1, encoding from faces")
    else:
      cursor.execute(
          "select image, identity, x0, y0, x1, y1, encoding from faces where identity = 'unknown'"
      )

    for row in cursor.fetchall():
      bounds = [int(row[2]), int(row[3]), int(row[4]), int(row[5])]
      encodings = np.array(json.loads(row[6]))

      yield row[0], bounds, row[1], encodings

  def job_status(self, image: Photo, job: str):
    """Check if a job is complete, according to the local database"""

    cursor = self.conn.cursor()
    cursor.execute(f"select {job} from jobs where image = ?", (image.path, ))

    row = cursor.fetchone()

    return row and bool(row[0])

  def register_google_photos_metadata(self, fpath: str, address: str, lat: str, lon: str):
    cursor = self.conn.cursor()
    cursor.execute("""
    update images
      set latitude = ?, longitude = ?, address = ?
      where fpath like '%' || ?;
    """, (lat, lon, address, fpath))
    self.conn.commit()

  def register_job_complete(self, image: Photo, job: str):
    """Register a job as complete in the local database"""

    cursor = self.conn.cursor()
    cursor.execute(
        f"""
        insert into jobs (image, {job})
        values (?, ?)
        on conflict(image) do update set {job} = 1
    """, (image.path, 1))
    self.conn.commit()

  def register_face_cluster(self, image: str, cluster: int):
    """Register a face cluster in the local database"""

    cursor = self.conn.cursor()
    cursor.execute(
        """
        update faces
        set identity = ?
        where image = ? and identity = 'unknown'
        """, (cluster, image))
    self.conn.commit()

  def register_faces(self, image: Photo, bounds: List[int], encoding: List):
    """Register a face in the local database"""

    json_encoding = json.dumps(encoding)

    cursor = self.conn.cursor()
    cursor.execute(
        """
        insert into faces (x0, y0, x1, y1, identity, image, encoding)
        values (?, ?, ?, ?, ?, ?, ?)
        """,
        (bounds[0], bounds[1], bounds[2], bounds[3], 'unknown', image.path, json_encoding))
    self.conn.commit()

  def register_thumbnail_url(self, image: Photo, url: str, format='webp'):
    """Register a thumbnail URL for an image in the local database"""

    target_column = 'thumbnail_url'
    if format == 'jpeg':
      target_column = 'thumbnail_url_jpeg'

    cursor = self.conn.cursor()
    cursor.execute(f"update images set {target_column} = ? where fpath = ?",
                   (url, image.path))
    self.conn.commit()

  def register_image_url(self, image: Photo, url: str, format='webp'):
    """"""

    target_column = 'image_url'
    if format == 'jpeg':
      target_column = 'image_url_jpeg'

    cursor = self.conn.cursor()
    cursor.execute(f"update images set {target_column} = ? where fpath = ?",
                   (url, image.path))
    self.conn.commit()

  def register_dates(self, fpath: str, min_date, max_date):
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
          images.fpath, images.tags, images.image_url, images.thumbnail_url, images.description as photo_description,
          images.date_time, images.f_number, images.focal_length, images.model,
          images.iso, images.blur, images.width, images.height,
          albums.album_name, albums.cover_image, albums.description, albums.min_date, albums.max_date, albums.geolocation
        from images
        inner join albums on images.album = albums.fpath
        where published = '1'
      """)

    folders = {}

    for row in cursor.fetchall():
      (fpath, tags, image_url, thumbnail_url, photo_description, date_time,
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
            'cover_image': os.path.join(dirname, cover_image),
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
            thumbnail_url.replace(SPACES_DOMAIN, '')
        })

    manifest = {'domain': SPACES_DOMAIN, 'folders': folders}

    with open(manifest_file, 'w') as conn:
      conn.write(json.dumps(manifest))

  def copy_metadata_file(self, metadata_path: str, manifest_path: str) -> None:
    """Copy the metadata file to the target destination"""

    manifest_dname = os.path.dirname(manifest_path)
    metadata_dst = os.path.join(manifest_dname, 'metadata.json')

    content = yaml.safe_load(open(metadata_path))

    with open(metadata_dst, 'w') as conn:
      conn.write(json.dumps(content))

  def close(self):
    """Close the local database connection"""

    self.conn.close()
