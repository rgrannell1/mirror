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
