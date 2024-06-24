
import json
from src.manifest import Manifest

IMAGES_HEADERS = [
  'fpath',
  'id',
  'tags',
  'description',
  'date_time',
  'f_number',
  'focal_length',
  'model',
  'iso',
  'blur',
  'width',
  'height',
  'image_url',
  'thumbnail_url',
  'thumbnail_data_url'
]

ALBUMS_HEADERS = [
  'album_name',
  'min_date',
  'max_date',
  'description',
  'image_count',
  'image_url',
  'thumbnail_url',
  'thumbnail_mosaic_url'
]

def add_id(row):
  return [row[0], str(hash(row[0]))] + row[1:]

class ImagesArtifacts:
  """Generate an artifact describing the images in the database."""

  @staticmethod
  def content(db: Manifest):
    cursor = db.conn.cursor()
    cursor.execute(f"""
      select
        fpath,
        'id',
        tags,
        description,
        date_time,
        f_number,
        focal_length,
        model,
        iso,
        blur,
        width,
        height,
        (
          select url from encoded_images
          where encoded_images.fpath = images.fpath
          and mimetype='image/webp' and role = 'full_image_lossless'
        ) as image_url,
        (
          select url from encoded_images
          where encoded_images.fpath = images.fpath
          and mimetype='image/webp' and role = 'thumbnail_lossless'
        ) as thumbnail_url,
        (
          select url from encoded_images
          where encoded_images.fpath = images.fpath
          and mimetype='image/bmp' and role = 'thumbnail_mosaic'
        ) as thumbnail_mosaic_url
      from images
      where published = '1'
    """)

    return json.dumps([IMAGES_HEADERS] + [add_id(row) for row in cursor.fetchall()])

class AlbumArtifacts:
  """Generate an artifact describing the albums in the database."""

  @staticmethod
  def content(db: Manifest):
    cursor = db.conn.cursor()
    cursor.execute("""
      select
        album_name as name,
        min_date,
        max_date,
        description,
        (
          select count(*) from images
          where images.album = albums.fpath
        ) as image_count,
        (
          select url from encoded_images
          where encoded_images.fpath = albums.cover_path
          and mimetype='image/webp' and role = 'full_image_lossless'
        ) as image_url,
        (
          select url from encoded_images
          where encoded_images.fpath = albums.cover_path
          and mimetype='image/webp' and role = 'thumbnail_lossless'
        ) as thumbnail_url,
        (
          select url from encoded_images
          where encoded_images.fpath = albums.cover_path
          and mimetype='image/bmp' and role = 'thumbnail_mosaic'
        ) as thumbnail_mosaic_url
        from albums;
    """)

    return json.dumps([ALBUMS_HEADERS] + [row for row in cursor.fetchall()])
