from dataclasses import dataclass
from typing import Generic, List, Protocol, Type, TypeVar, Any


T = TypeVar("T", bound="IModel", covariant=True)


class IModel(Protocol, Generic[T]):
    """Represents an entity stored in the database, and the method for reading it from a
    database row. Implementations represent some chunk of data"""

    @classmethod
    def from_row(cls: Type[T], row: List) -> T:
        pass


@dataclass
class AlbumMetadataModel:
    src: str
    src_type: str
    relation: str
    target: str | None

    @classmethod
    def from_row(cls, row: List[Any]) -> "AlbumMetadataModel":
        return cls(
            src=row[0],
            src_type=row[1],
            relation=row[2],
            target=row[3],
        )
