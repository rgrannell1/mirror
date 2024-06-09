"""The core-logic of Mirror."""

from src.commands.tag import tag
from src.commands.list_tags import list_tags
from src.commands.list_tagfiles import list_tagfiles
from src.commands.list_photos import list_photos
from src.commands.publish import publish
from src.commands.feed import feed
from src.commands.tag_faces import tag_faces


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
  def list_photos(dir: str, metadata_path: str, tag: str) -> None:
    list_photos(dir, metadata_path, tag)

  @staticmethod
  def publish(dir: str, metadata_path: str, manifest_path: str) -> None:
    publish(dir, metadata_path, manifest_path)

  @staticmethod
  def feed(dir: str, metadata_path: str, out_dir: str) -> None:
    feed(dir, metadata_path, out_dir)

  @staticmethod
  def tag_faces(dir: str, metadata_path: str) -> None:
    tag_faces(dir, metadata_path)
