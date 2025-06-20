from dataclasses import dataclass
import sqlite3
from typing import Iterator, List, Optional, Protocol
from src.model import IModel


@dataclass
class PhotoAnswerModel(IModel):
    """Represents an answer refering to some photo in the database"""

    contentId: str
    questionId: str
    answerId: Optional[str]
    answer: Optional[str]

    @classmethod
    def from_row(cls, row: List) -> "PhotoAnswerModel":
        (contentId, questionId, answerId, answer) = row

        return PhotoAnswerModel(
            contentId=contentId,
            questionId=questionId,
            answerId=answerId,
            answer=answer,
        )

    def relation(self) -> Optional[str]:
        qid = self.questionId

        if qid == "q01":
            return "style"
        elif qid == "q02":
            return "wildlife"
        elif qid == "q03" or qid == "q03_5":
            return "living_conditions"
        elif qid == "q04":
            return "amphibian"
        elif qid == "q05":
            return "rating"
        elif qid == "q06":
            return "in_flight"
        elif qid == "q07":
            return "has_body_of_water"
        elif qid == "q08":
            return "water_feature"
        elif qid == "q09":
            return "cityscape_focus"
        elif qid == "q10":
            return "city_water_feature"
        elif qid == "q11":
            return "summary"
        elif qid == "q12":
            return "vehicle"
        elif qid == "q13":
            return "plane_model"
        elif qid == "q14":
            return "bird_binomial"
        elif qid == "q15":
            return "mammal_binomial"
        elif qid == "q16":
            return "water_name"
        elif qid == "q17":
            return "water_type"

        return None


class ILinnaeusDatabase(Protocol):
    """Interact with a linnaeus database"""

    def list_photo_answers(self) -> Iterator[PhotoAnswerModel]: ...


class SqliteLinnaeusDatabase(ILinnaeusDatabase):
    """Interact with a sqlite linnaeus database"""

    conn: sqlite3.Connection

    def __init__(self, fpath: str) -> None:
        self.conn = sqlite3.connect(fpath)

    def list_photo_answers(self) -> Iterator[PhotoAnswerModel]:
        for row in self.conn.execute("select * from image_answers"):
            yield PhotoAnswerModel.from_row(row)
