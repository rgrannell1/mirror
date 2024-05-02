"""An RSS feed for this site, at the album-level to avoid feed-bloat."""

from typing import List

from src.photo import Photo
import datetime
import re

class JSONFeed:
  @classmethod
  def author(self):
    return {
      'name': 'Róisín Grannell',
      'url': 'https://rgrannell.xyz',
      'avatar': 'https://rgrannell.xyz/me.png'
    }

  @classmethod
  def rfc_date(cls, date: str) -> str:
    pattern = r'^\d{4}:\d{2}:\d{2} \d{2}:\d{2}:\d{2}$'
    if not re.match(pattern, date):
      raise ValueError("Invalid date format. Expected format: 'YYYY:MM:DD HH:MM:SS'")

    date_obj = datetime.datetime.strptime(date, "%Y:%m:%d %H:%M:%S")
    return date_obj.strftime("%Y-%m-%dT%H:%M:%SZ")

  @classmethod
  def image(cls, db, image: Photo):
    image_url, thumbnail_url, date_time, _ = db.image_metadata(image.path)

    return {
      "id": image_url,
      "url": image_url,
      "image": thumbnail_url,
      "date_published": JSONFeed.rfc_date(date_time)
    }

  @classmethod
  def tag_feed(cls, db, tag: str, images: List[Photo]):
    return {
      'version': 'https://jsonfeed.org/version/1',
      'title': f'📷 {tag} — photos.rgrannell.xyz',
      'home_page_url': 'https://photos.rgrannell.xyz',
      'feed_url': f'https://photos.rgrannell.xyz/feeds/{tag}.json',
      'description': f'📷 {tag} — photos.rgrannell.xyz',
      'icon': 'https://photos.rgrannell.xyz/icons/android-chrome-512x512.png',
      'favicon': 'https://photos.rgrannell.xyz/favicon.ico',
      'author': JSONFeed.author(),
      'language': 'en-IE',
      'items': [JSONFeed.image(db, image) for image in images]
    }

  @classmethod
  def feed(cls, db, tag: str, images: List[Photo]):
    return {
      'version': 'https://jsonfeed.org/version/1',
      'title': f'📷 photos.rgrannell.xyz',
      'home_page_url': 'https://photos.rgrannell.xyz',
      'feed_url': 'https://photos.rgrannell.xyz/feeds/index.json',
      'description': f'📷 photos.rgrannell.xyz',
      'icon': 'https://photos.rgrannell.xyz/icons/android-chrome-512x512.png',
      'favicon': 'https://photos.rgrannell.xyz/favicon.ico',
      'author': JSONFeed.author(),
      'language': 'en-IE',
      'items': [JSONFeed.image(db, image) for image in images]
    }
