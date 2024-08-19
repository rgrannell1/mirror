"""The core-logic of Mirror."""

from typing import Optional
from src.commands.tag import tag
from src.commands.list_tags import list_tags
from src.commands.list_tagfiles import list_tagfiles
from src.commands.show_tagfiles import show_tagfiles
from src.commands.list_photos import list_photos
from src.commands.publish import publish
from src.commands.feed import feed
from src.commands.add_google_photos_metadata import add_google_photos_metadata
from src.commands.add_google_vision_metadata import add_google_vision_metadata
from src.commands.add_answers import add_answers

class Mirror:
  """The core-logic of Mirror. Invoked by the CLI"""

  @staticmethod
  def tag(dir: str, metadata_path: str) -> None:
    tag(dir, metadata_path)

  @staticmethod
  def list_tags(dir: str, opts) -> None:
    list_tags(dir, opts)

  @staticmethod
  def list_tagfiles(dir: str, tag: str) -> None:
    list_tagfiles(dir)

  @staticmethod
  def show_tagfiles(dir: str, tag: str) -> None:
    show_tagfiles(dir, tag)

  @staticmethod
  def list_photos(dir: str, metadata_path: str, tag: str, start: Optional[str], end: Optional[str]) -> None:
    list_photos(dir, metadata_path, tag, start, end)

  @staticmethod
  def publish(dir: str, metadata_path: str, manifest_path: str) -> None:
    publish(dir, metadata_path, manifest_path)

  @staticmethod
  def feed(dir: str, metadata_path: str, out_dir: str) -> None:
    feed(dir, metadata_path, out_dir)

  @staticmethod
  def add_google_photos_metadata(dir: str, metadata_path: str, google_photos_file: str) -> None:
    add_google_photos_metadata(dir, metadata_path, google_photos_file)
    add_google_photos_metadata(dir, metadata_path, google_photos_file)

  @staticmethod
  def add_google_vision_metadata(dir: str, metadata_path: str) -> None:
    add_google_vision_metadata(dir, metadata_path)

  @staticmethod
  def add_answers(dir: str, metadata_path: str, images_db: str, albums_db: str) -> None:
    add_answers(dir, metadata_path, images_db, albums_db)
