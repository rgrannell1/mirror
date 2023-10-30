
from src.commands.init import init
from src.commands.tag import tag
from src.commands.list_tags import list_tags
from src.commands.list_photos import list_photos
from src.commands.publish import publish

class Mirror:
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
  def publish(dir: str) -> None:
    publish(dir)
