"""SQL tables for storing album information"""

PHOTOS_TABLE = """
create table if not exists photos (
  fpath text primary key,
  dpath text not null
);
"""

PHASHES_TABLE = """
create table if not exists phashes (
  fpath text primary key,
  phash text
);
"""

VIDEOS_TABLE = """
create table if not exists videos (
  fpath text primary key,
  dpath text not null
);
"""

EXIF_TABLE = """
create table if not exists exif (
  fpath            text primary key,
  created_at       text,
  f_stop           text,
  focal_length     text,
  model            text,
  exposure_time    text,
  iso              text,
  width            text,
  height           text,

  foreign key (fpath) references photos(fpath) on delete cascade
);
"""

ENCODED_PHOTOS_TABLE = """
create table if not exists encoded_photos (
  fpath       text not null,
  mimetype    text not null,
  role        text not null,
  url         text not null,

  primary key (fpath, mimetype, role),
  foreign key (fpath) references photos(fpath) on delete cascade
);
"""

ENCODED_VIDEO_TABLE = """
create table if not exists encoded_videos (
  fpath          text not null,
  mimetype       text not null,
  role           text not null,
  url            text not null,

  primary key (fpath, mimetype, role),
  foreign key (fpath) references videos(fpath) on delete cascade
);
"""

ALBUM_CONTENTS_TABLE = """
create view if not exists album_contents as
  select fpath, dpath, "photo" as type from photos
  union all
  select fpath, dpath, "video" as type from videos
  order by dpath;
"""

ALBUM_DATA_VIEW = """
CREATE VIEW IF NOT EXISTS album_data AS
WITH date_range AS (
    SELECT
        photos.dpath,
        MIN(exif.created_at) AS min_date,
        MAX(exif.created_at) AS max_date
    FROM photos
    JOIN exif ON photos.fpath = exif.fpath
    GROUP BY photos.dpath
),
cover_photos AS (
    SELECT
        dpath,
        MAX(fpath) AS cover
    FROM photos
    WHERE fpath LIKE '%+cover%'
    GROUP BY dpath
)
SELECT
    (
      select target from media_metadata_table
      where src = media.dpath and relation = 'permalink') as id,
    (
      select target from media_metadata_table
      where src = media.dpath and relation = 'title') as name,
      media.dpath,
      coalesce(photo_count.photos, 0) as photos_count,
      coalesce(video_count.videos, 0) as videos_count,
      coalesce(date_range.min_date, null) as min_date,
      coalesce(date_range.max_date, null) as max_date,
      coalesce(thumbnail_lossy.url, null) as thumbnail_url,
      coalesce(thumbnail_data.url, null) as thumbnail_mosaic_url,
    (SELECT target FROM media_metadata_table
     WHERE src = media.dpath AND relation = 'county') AS flags,
    (SELECT target FROM media_metadata_table
     WHERE src = media.dpath AND relation = 'summary') AS description
FROM (
    SELECT dpath FROM photos
    UNION
    SELECT dpath FROM videos
) media
LEFT JOIN (
    SELECT
        dpath,
        COUNT(*) AS photos
    FROM photos
    GROUP BY dpath
) photo_count ON media.dpath = photo_count.dpath
LEFT JOIN (
    SELECT
        dpath,
        COUNT(*) AS videos
    FROM videos
    GROUP BY dpath
) video_count ON media.dpath = video_count.dpath
LEFT JOIN date_range
  ON media.dpath = date_range.dpath
LEFT JOIN cover_photos
  ON media.dpath = cover_photos.dpath
LEFT JOIN encoded_photos thumbnail_lossy
    ON cover_photos.cover = thumbnail_lossy.fpath
    AND thumbnail_lossy.role = 'thumbnail_lossy'
LEFT JOIN encoded_photos thumbnail_data
    ON cover_photos.cover = thumbnail_data.fpath
    AND thumbnail_data.role = 'thumbnail_data_url';
"""

PHOTO_DATA_VIEW = """
create view if not exists photo_data as
  select
    photos.fpath,
    album_data.id as album_id,
    "" as tags,
    coalesce(thumbnail_lossy.url, null) as thumbnail_url,
    coalesce(thumbnail_data.url, null) as thumbnail_mosaic_url,
    coalesce(full_image_png.url, null) as png_url,
    coalesce(full_image.url, null) as full_image,
    coalesce(exif.created_at, null) as created_at,
    coalesce(phashes.phash, null) as phash
  from photos
  left join album_data
    on photos.dpath = album_data.dpath
  left join encoded_photos thumbnail_lossy
    on photos.fpath = thumbnail_lossy.fpath and thumbnail_lossy.role = 'thumbnail_lossy'
  left join encoded_photos thumbnail_data
    on photos.fpath = thumbnail_data.fpath and thumbnail_data.role = 'thumbnail_data_url'
  left join encoded_photos full_image
    on photos.fpath = full_image.fpath and full_image.role = 'full_image_lossless'
  left join encoded_photos full_image_png
    on photos.fpath = full_image_png.fpath and full_image_png.role = 'full_image_png'
  left join exif
    on photos.fpath = exif.fpath
  left join phashes
    on photos.fpath = phashes.fpath
  order by photos.fpath desc;
"""

VIDEO_DATA_VIEW = """
create view if not exists video_data as
  select
    videos.fpath,
    album_data.id as album_id,
    "" as tags,
    "" as description,
    coalesce(video_url_unscaled.url, null) as video_url_unscaled,
    coalesce(video_url_1080p.url, null) as video_url_1080p,
    coalesce(video_url_720p.url, null) as video_url_720p,
    coalesce(video_url_480p.url, null) as video_url_480p,
    coalesce(poster_url.url, null) as poster_url
  from videos
  left join album_data
    on videos.dpath = album_data.dpath
  left join encoded_videos video_url_unscaled
    on videos.fpath = video_url_unscaled.fpath and video_url_unscaled.role = 'video_libx264_unscaled'
  left join encoded_videos video_url_1080p
    on videos.fpath = video_url_1080p.fpath and video_url_1080p.role = 'video_libx264_1080p'
  left join encoded_videos video_url_720p
    on videos.fpath = video_url_720p.fpath and video_url_720p.role = 'video_libx264_720p'
  left join encoded_videos video_url_480p
    on videos.fpath = video_url_480p.fpath and video_url_480p.role = 'video_libx264_480p'
  left join encoded_photos poster_url
    on videos.fpath = poster_url.fpath and poster_url.role = 'video_thumbnail_webp'
  order by videos.fpath desc;
"""

# Stores semantic data about the media in this database, collected from
# Linnaues and other sources
MEDIA_METADATA_TABLE = """
create table if not exists media_metadata_table (
  src         text not null,
  src_type    text not null,
  relation    text not null,
  target      text,

  primary key (src, src_type, relation, target)
);
"""

PHOTO_METADATA_TABLE = """
create table if not exists photo_metadata_table (
  phash       text not null,
  src_type    text not null,
  relation    text not null,
  target      text,

  primary key (phash, src_type, relation, target)
);
"""
