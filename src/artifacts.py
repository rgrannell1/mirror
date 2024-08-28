
import re
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
  'rating',
  'subject'
]

ALBUMS_HEADERS = [
  'id',
  'album_name',
  'min_date',
  'max_date',
  'description',
  'image_count',
  'thumbnail_url',
  'thumbnail_mosaic_url',
  'flags'
]

class ImagesArtifacts:
  """Generate an artifact describing the images in the database."""

  @staticmethod
  def content(db: Manifest):
    cursor = db.conn.cursor()
    cursor.execute(f"""
      select
        images.fpath,
        albums.permalink,
        tags,
        (
          select group_concat(target, ',') from photo_relations
          where relation = 'contains' and photo_relations.source = images.fpath
        ) as tags_v2,
        images.description,
        images.date_time,
        images.f_number,
        images.focal_length,
        images.model,
        images.iso,
        images.blur,
        images.shutter_speed,
        images.width,
        images.height,
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
        ) as image_url,
        (
          select target from photo_relations
          where photo_relations.source = images.fpath and photo_relations.relation = 'rating'
          limit 1
        ) as rating,
        (
          select target from photo_relations
          where photo_relations.source = images.fpath and photo_relations.relation = 'photo_subject'
          limit 1
        ) as subject

      from images
      join albums on albums.fpath = images.album
      where published = '1'
    """)

    rows = [IMAGES_HEADERS]

    for row in cursor.fetchall():
      fpath, album_permalink, tags, tags_v2, description, *rest = row

      if (not album_permalink):
        raise ValueError(f"did not find a permalink for image '{fpath}'. Please update {fpath}/tags.md")

      joined_tags = {tag.strip() for tag in re.split(r'\s*,\s*', tags if tags else '') + re.split(r'\s*,\s*', tags_v2 if tags_v2 else '') if tag}

      rows.append([
        fpath,
        str(hash(fpath)),
        album_permalink,
        ','.join(joined_tags),
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
        (
          select target from photo_relations
          where source = albums.fpath and relation = 'permalink'
        ),
        (
          select target from photo_relations
          where source = albums.fpath and relation = 'album_name'
        ),
        min_date,
        max_date,
        coalesce((
          select target from photo_relations
          where source = albums.fpath and relation = 'description'
        ), '') as description,
        (
          select count(*) from images
          where images.album = albums.fpath and published = '1'
        ) as image_count,
        (
          select url from encoded_images
          where encoded_images.fpath = albums.cover_path
          and mimetype='image/webp' and role = 'thumbnail_lossy_v2'
        ) as thumbnail_url,
        (
          select url from encoded_images
          where encoded_images.fpath = albums.cover_path
          and mimetype='image/bmp' and role = 'thumbnail_mosaic'
        ) as thumbnail_mosaic_url,
        (
          select group_concat(target, ',')
          from photo_relations
          where relation = 'flag' and source in
          (
            select target from photo_relations
            where source = albums.fpath and relation = 'country'
          )
        ) as flags

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
      if not row[0]:
        messages.append(f"did not find a permalink for album '{row[1]}'. Please update {row[0]}/tags.md")
        continue

      if not row[6]:
        messages.append(f"did not find a cover image for album '{row[1]}'. Please update {row[0]}/tags.md")
        continue

      permalink, album_name, min_date, max_date, description, *rest = row

      rows.append([
        permalink,
        album_name,
        min_date,
        max_date,
        markdown.markdown(description)
      ] + rest)

    if messages:
      print('\n'.join(messages), file=sys.stderr)

    return json.dumps(rows)

class MetadataArtifacts:
  @staticmethod
  def get_subsumed(db: Manifest, is_a: str):
    cursor = db.conn.cursor()
    cursor.execute(f"""
    select distinct(source) from photo_relations
      where relation = 'is-a' and target = ?
      order by source;
    """, (is_a,))

    children = set()

    for row in cursor.fetchall():
      sources = row[0].split(',')
      for source in sources:
        children.add(source)

    return sorted(list(children))

  @staticmethod
  def content(db: Manifest):
    return {
      'Bird': {
        'children': MetadataArtifacts.get_subsumed(db, 'Bird')
      },
      'Plane': {
        'children': MetadataArtifacts.get_subsumed(db, 'Plane')
      },
      'Helicopter': {
        'children': MetadataArtifacts.get_subsumed(db, 'Helicopter')
      },
      'Mammal': {
        'children': MetadataArtifacts.get_subsumed(db, 'Mammal')
      }
    }
