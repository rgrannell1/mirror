from typing import List, Optional, Protocol, Tuple, Type, TypeVar, TypedDict


T = TypeVar("T", bound="IModel")


class IModel(Protocol):
    """Represents an entity stored in the database, and the method for reading it from a
    database row. Implementations represent some chunk of data"""

    @classmethod
    def from_row(cls: Type[T], row: List) -> T: ...


class VideoEncodingConfig(TypedDict):
    bitrate: str
    width: Optional[int]
    height: Optional[int]


VideoEncoding = Tuple[str, VideoEncodingConfig]
