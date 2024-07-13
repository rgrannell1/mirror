
import sys
import json
import markdown
from src.manifest import Manifest

IMAGES_HEADERS = [
  'fpath',
  'id',
  'album_id',
  'tags',
  'description',
  'date_time',
  'f_number',
  'focal_length',
  'model',
  'iso',
  'blur',
  'shutter_speed',
  'width',
  'height',
  'thumbnail_url',
  'thumbnail_data_url',
  'image_url',
]

ALBUMS_HEADERS = [
  'id',
  'album_name',
  'min_date',
  'max_date',
  'description',
  'image_count',
  'image_url',
  'thumbnail_url',
  'thumbnail_mosaic_url'
]

class ImagesArtifacts:
  """Generate an artifact describing the images in the database."""

  @staticmethod
  def content(db: Manifest):
    cursor = db.conn.cursor()
    cursor.execute(f"""
      select
        fpath,
        album,
        tags,
        description,
        date_time,
        f_number,
        focal_length,
        model,
        iso,
        blur,
        shutter_speed,
        width,
        height,
        (
          select url from encoded_images
          where encoded_images.fpath = images.fpath
          and mimetype='image/webp' and role = 'thumbnail_lossless'
        ) as thumbnail_url,
        (
          select url from encoded_images
          where encoded_images.fpath = images.fpath
          and mimetype='image/bmp' and role = 'thumbnail_mosaic'
        ) as thumbnail_mosaic_url,
        (
          select url from encoded_images
          where encoded_images.fpath = images.fpath
          and mimetype ='image/webp' and role = 'full_image_lossless'
        ) as image_url

      from images
      where published = '1'
    """)

    rows = [IMAGES_HEADERS]

    for row in cursor.fetchall():
      fpath, album, tags, description, *rest = row
      rows.append([
        fpath,
        str(hash(fpath)),
        str(hash(album)),
        tags,
        markdown.markdown(description)
      ] + rest)

    return json.dumps(rows)

class AlbumArtifacts:
  """Generate an artifact describing the albums in the database."""

  @staticmethod
  def content(db: Manifest):
    cursor = db.conn.cursor()
    cursor.execute("""
      select
        fpath,
        album_name as name,
        min_date,
        max_date,
        description,
        (
          select count(*) from images
          where images.album = albums.fpath and published = '1'
        ) as image_count,
        (
          select url from encoded_images
          where encoded_images.fpath = albums.cover_path
          and mimetype='image/webp' and role = 'full_image_lossless'
        ) as image_url,
        (
          select url from encoded_images
          where encoded_images.fpath = albums.cover_path
          and mimetype='image/webp' and role = 'thumbnail_lossy_v2'
        ) as thumbnail_url,
        (
          select url from encoded_images
          where encoded_images.fpath = albums.cover_path
          and mimetype='image/bmp' and role = 'thumbnail_mosaic'
        ) as thumbnail_mosaic_url
        from albums
        where albums.fpath in (
            select distinct images.album
            from images
            where images.published = '1'
        );
    """)

    messages = []
    rows = [ALBUMS_HEADERS]

    for row in cursor.fetchall():
      if not row[6]:
        messages.append(f"did not find a cover image for album '{row[1]}'. Please update {row[0]}/tags.md")
        continue

      fpath, album_name, min_date, max_date, description, *rest = row

      rows.append([
        str(hash(fpath)),
        album_name,
        min_date,
        max_date,
        markdown.markdown(description)
      ] + rest)

    if messages:
      print('\n'.join(messages), file=sys.stderr)

    return json.dumps(rows)
