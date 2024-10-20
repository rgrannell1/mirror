ENCODED_IMAGE_TABLE = """
create table if not exists encoded_images (
  fpath    text not null,
  mimetype text not null,
  role     text not null,
  url      text not null,

  primary key (fpath, mimetype, role)
)
"""

ENCODED_VIDEO_TABLE = """
create table if not exists encoded_videos (
  fpath          text not null,
  mimetype       text not null,
  role           text not null,
  url            text not null,

  primary key (fpath, mimetype, role)
)
"""

IMAGES_TABLE = """
create table if not exists images (
  fpath              text primary key,
  tags               text,
  metadata_hash      text,
  exif_hash          text,
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

VIDEOS_TABLE = """
create table if not exists videos (
  fpath              text primary key,
  tags               text,
  published          boolean,
  description        text,
  album              text,
  share_audio        text,

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

PHOTO_RELATIONS_TABLE = """
create table if not exists photo_relations (
  source    text,
  relation  text,
  target    text,

  primary key (source, relation, target)
)
"""

ALBUMS_ARTIFACT_VIEW = """
create view if not exists albums_artifact as
select
  (
    select target from photo_relations
    where source = albums.fpath and relation = 'permalink'
  ) as permalink,
  (
    select target from photo_relations
    where source = albums.fpath and relation = 'album_name'
  ) as name,
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
  ) and name != "Misc";
"""

VIDEOS_ARTIFACT_VIEW = """
create view if not exists videos_artifact as
  select
    videos.fpath,
    albums.permalink,
    (
      select group_concat(target, ',') from photo_relations
      where relation = 'contains' and photo_relations.source = videos.fpath
    ) as tags,
    (
      select target from photo_relations
      where relation = 'description' and photo_relations.source = videos.fpath
      limit 1
    ) as description,
    (
      select url from encoded_videos
      where encoded_videos.fpath = videos.fpath
      and role = 'video_libx264_unscaled'
    ) as video_url_unscaled,
    (
      select url from encoded_videos
      where encoded_videos.fpath = videos.fpath
      and role = 'video_libx264_1080p'
    ) as video_url_1080p,
    (
      select url from encoded_videos
      where encoded_videos.fpath = videos.fpath
      and role = 'video_libx264_720p'
    ) as video_url_720p,
    (
      select url from encoded_videos
      where encoded_videos.fpath = videos.fpath
      and role = 'video_libx264_480p'
    ) as video_url_480p,
    (
      select url from encoded_images
      where encoded_images.fpath = videos.fpath
      and role = 'video_thumbnail_webp'
    ) as poster_url

    from videos
    join albums on albums.fpath = videos.album
    where published = '1'
"""

IMAGES_ARTIFACT_VIEW = """
create view if not exists images_artifact as
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
"""
