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

ALBUM_CONTENTS_VIEW = """
create view if not exists view_album_contents as
  select fpath, dpath, "photo" as type from photos
  union all
  select fpath, dpath, "video" as type from videos
  order by dpath;
"""

ALBUM_DATA_VIEW = """
CREATE VIEW IF NOT EXISTS view_album_data AS
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
      coalesce(mosaic_colours.url, null) as mosaic_colours,
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
    AND thumbnail_data.role = 'thumbnail_data_url'
LEFT JOIN encoded_photos mosaic_colours
    ON cover_photos.cover = mosaic_colours.fpath
    AND mosaic_colours.role = 'thumbnail_mosaic';
"""

PHOTO_DATA_VIEW = """
create view if not exists view_photo_data as
  select
    photos.fpath,
    view_album_data.id as album_id,
    "" as tags,
    coalesce(thumbnail_lossy.url, null) as thumbnail_url,
    coalesce(thumbnail_data.url, null) as thumbnail_mosaic_url,
    coalesce(mosaic_colours.url, null) as mosaic_colours,
    coalesce(full_image_png.url, null) as png_url,
    coalesce(full_image.url, null) as full_image,
    coalesce(mid_image_lossy.url, null) as mid_image_lossy,
    coalesce(exif.created_at, null) as created_at,
    coalesce(phashes.phash, null) as phash
  from photos
  left join view_album_data
    on photos.dpath = view_album_data.dpath
  left join encoded_photos thumbnail_lossy
    on photos.fpath = thumbnail_lossy.fpath and thumbnail_lossy.role = 'thumbnail_lossy'
  left join encoded_photos thumbnail_data
    on photos.fpath = thumbnail_data.fpath and thumbnail_data.role = 'thumbnail_data_url'
  left join encoded_photos full_image
    on photos.fpath = full_image.fpath and full_image.role = 'full_image_lossless'
  left join encoded_photos full_image_png
    on photos.fpath = full_image_png.fpath and full_image_png.role = 'full_image_png'

  left join encoded_photos mid_image_lossy
    on photos.fpath = mid_image_lossy.fpath and mid_image_lossy.role = 'mid_image_lossy'


  left join encoded_photos mosaic_colours
    on photos.fpath = mosaic_colours.fpath and mosaic_colours.role = 'thumbnail_mosaic'
  left join exif
    on photos.fpath = exif.fpath
  left join phashes
    on photos.fpath = phashes.fpath
  order by photos.fpath desc;
"""

VIDEO_DATA_VIEW = """
create view if not exists view_video_data as
  select
    videos.fpath,
    view_album_data.id as album_id,
    "" as tags,
    "" as description,
    coalesce(video_url_unscaled.url, null) as video_url_unscaled,
    coalesce(video_url_1080p.url, null) as video_url_1080p,
    coalesce(video_url_720p.url, null) as video_url_720p,
    coalesce(video_url_480p.url, null) as video_url_480p,
    coalesce(poster_url.url, null) as poster_url
  from videos
  left join view_album_data
    on videos.dpath = view_album_data.dpath
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

# target:
#
PHOTO_METADATA_TABLE = """
create table if not exists photo_metadata_table (
  phash       text not null,
  src_type    text not null,
  relation    text not null,
  target      text,

  primary key (phash, src_type, relation, target)
);
"""

# shape photo metadata into a columnar format
PHOTO_METADATA_VIEW = """
create view if not exists view_photo_metadata as
  select * from (with aggregated as (
    select
      phash,
      coalesce(group_concat(case when relation = 'style' then target end, ', '), '') as genre,
      coalesce(group_concat(case when relation = 'rating' then target end, ', '), '') as rating,
      coalesce(group_concat(case when relation = 'location' then target end, ', '), '') as places,
      coalesce(group_concat(case when relation = 'summary' then target end, ', '), '') as description,
      coalesce(group_concat(case when relation = 'subject' then target end, ', '), '') as subjects,
      coalesce(group_concat(case when relation = 'cover' then target end, ', '), '') as covers
    from
      photo_metadata_table
    where
      relation in ('style', 'rating', 'location', 'summary', 'subject', 'cover')
    group by
      phash
  )

  select * from aggregated

  union all

  select
    p.phash,
    '' as genre,
    '' as rating,
    '' as places,
    '' as description,
    '' as subjects,
    '' as covers
  from
    phashes p
  left join aggregated a on p.phash = a.phash
  where
    a.phash is null);
"""

# TODO: dedupe by `phashes.phash`
PHOTO_METADATA_SUMMARY = """
create view if not exists view_photo_metadata_summary as
    with photo_information as (
      select
          phashes.fpath,
          genre,
          rating,
          places,
          description,
          subjects,
          covers
      from
          view_photo_metadata as pv
      left join phashes on
          pv.phash = phashes.phash
    )
    select
      photo_information.fpath as fpath,
      encoded_photos.url as url,
      view_album_data.name as name,
      genre,
      rating,
      places,
      photo_information.description as description,
      subjects,
      covers
    from
      photo_information
    inner join view_album_contents on
      photo_information.fpath = view_album_contents.fpath
    inner join view_album_data on
      view_album_data.dpath = view_album_contents.dpath
    inner join encoded_photos on
      photo_information.fpath = encoded_photos.fpath
      and role = 'thumbnail_lossy'
    order by name;
"""

GEONAME_TABLE = """
create table if not exists geonames (
  id      text not null primary key,
  data    text not null
);
"""

BINOMIALS_WIKIDATA_ID_TABLE = """
create table if not exists binomials_wikidata_id (
  binomial text not null primary key,
  qid     text
);
"""

WIKIDATA_TABLE = """
create table if not exists wikidata (
  id      text not null primary key,
  data    text not null
);
"""
