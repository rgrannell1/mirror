"""The core-logic of Mirror."""

from src.commands.init import init
from src.commands.tag import tag
from src.commands.list_tags import list_tags
from src.commands.list_photos import list_photos
from src.commands.publish import publish
from src.commands.feed import feed

class Mirror:
  """The core-logic of Mirror."""

  @staticmethod
  def init(dir: str) -> None:
    init(dir)

  @staticmethod
  def tag(dir: str, metadata_path: str) -> None:
    tag(dir, metadata_path)

  @staticmethod
  def list_tags(dir: str) -> None:
    list_tags(dir)

  @staticmethod
  def list_photos(dir: str, tag: str) -> None:
    list_photos(dir, tag)

  @staticmethod
  def publish(dir: str, manifest_path: str) -> None:
    publish(dir, manifest_path)

  @staticmethod
  def feed(dir: str, feed_path: str) -> None:
    feed(dir, feed_path)
