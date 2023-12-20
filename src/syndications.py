"""An RSS feed for this site, at the album-level to avoid feed-bloat."""

from typing import List

class JSONFeed:
  @classmethod
  def author(self):
    return {
      'name': 'Róisín Grannell',
      'url': 'https://rgrannell.xyz',
      'avatar': 'https://rgrannell.xyz/me.png'
    }

  @classmethod
  def album(cls, album: dict):
    metadata = album.get_metadata()

    return {
      'id': '',
      'url': 'https://photos.rgrannell.xyz/albums/album-id',
      'external_url': 'https://photos.rgrannell.xyz/albums/album-id',
      'title': 'album-title',
      'tags': ['photo-album'],
      'language': 'en-IE',
      'image': 'cover_url',
      'banner_image': 'cover_url',
      'authors': [JSONFeed.author()],
      'date_published': '',
      'date_modified': ''
    }

  @classmethod
  def feed(cls, albums: List):
    return {
      'version': 'https://jsonfeed.org/version/1',
      'title': '📷 photos.rgrannell.xyz',
      'home_page_url': 'https://photos.rgrannell.xyz',
      'feed_url': 'https://photos.rgrannell.xyz/feed.json',
      'description': 'A JSONFeed of my photo-album updates',
      'icon': 'https://photos.rgrannell.xyz/icons/android-chrome-512x512.png',
      'favicon': 'https://photos.rgrannell.xyz/favicon.ico',
      'author': JSONFeed.author(),
      'language': 'en-IE',
      'items': [JSONFeed.album(album) for album in albums]
    }
