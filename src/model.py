from typing import Generic, List, Protocol, Type, TypeVar


T = TypeVar("T", bound="IModel", covariant=True)


class IModel(Protocol, Generic[T]):
    """Represents an entity stored in the database, and the method for reading it from a
    database row. Implementations represent some chunk of data"""

    @classmethod
    def from_row(cls: Type[T], row: List) -> T:
        ...
