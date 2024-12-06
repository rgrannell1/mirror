
from dataclasses import dataclass
import sqlite3
from typing import Iterator, List, Optional, Protocol
from model import IModel

@dataclass
class AlbumAnswerModel(IModel):

  contentId: str
  questionId: str
  answerId: Optional[str]
  answer: Optional[str]

  @classmethod
  def from_row(cls, row: List) -> "AlbumAnswerModel":
    (contentId, questionId, answerId, answer) = row

    return AlbumAnswerModel(
      contentId=contentId,
      questionId=questionId,
      answerId=answerId,
      answer=answer,
    )

class ILinnaeusDatabase(Protocol):
  """Interact with a linnaeus database"""

  def list_album_answers(self) -> Iterator[AlbumAnswerModel]:
    pass


class SqliteLinnaeusDatabase(ILinnaeusDatabase):
  conn: sqlite3.Connection

  def __init__(self, fpath: str) -> None:
      self.conn = sqlite3.connect(fpath)

  def list_album_answers(self) -> Iterator[AlbumAnswerModel]:
    for row in self.conn.execute("select * from album_answers"):
      yield AlbumAnswerModel.from_row(row)
