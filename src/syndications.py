"""An RSS feed for this site, at the album-level to avoid feed-bloat."""

from typing import List

from src.photo import Photo
from src.constants import PERSONAL_URL, PHOTOS_URL
import datetime
import re

class JSONFeed:
  @classmethod
  def author(self):
    return {
      'name': 'Róisín Grannell',
      'url': PERSONAL_URL,
      'avatar': f'{PERSONAL_URL}/me.png'
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
      'title': f'📷 {tag} — {PHOTOS_URL}',
      'home_page_url': PHOTOS_URL,
      'feed_url': f'{PHOTOS_URL}/feeds/{tag}.json',
      'description': f'📷 {tag} — photos.rgrannell.xyz',
      'icon': f'{PHOTOS_URL}/icons/android-chrome-512x512.png',
      'favicon': f'{PHOTOS_URL}/favicon.ico',
      'author': JSONFeed.author(),
      'language': 'en-IE',
      'items': [JSONFeed.image(db, image) for image in images]
    }

  @classmethod
  def feed(cls, db, images: List[Photo]):
    return {
      'version': 'https://jsonfeed.org/version/1',
      'title': f'📷 photos.rgrannell.xyz',
      'home_page_url': f'{PHOTOS_URL}',
      'feed_url': f'{PHOTOS_URL}/feeds/index.json',
      'description': f'📷 photos.rgrannell.xyz',
      'icon': f'{PHOTOS_URL}/icons/android-chrome-512x512.png',
      'favicon': f'{PHOTOS_URL}/favicon.ico',
      'author': JSONFeed.author(),
      'language': 'en-IE',
      'items': [JSONFeed.image(db, image) for image in images]
    }
