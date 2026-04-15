"""Parse [[trips]] from things.toml into TripRow objects (with line tracking for editing)."""

from collections.abc import Iterator
from dataclasses import dataclass

from .loader import THINGS_PATH

EDITABLE_COLUMNS = ["contains_album"]

# Lines paired with their 1-based position in the source file
_NumberedLines = list[tuple[int, str]]


@dataclass
class TripRow:
    trip_id: str
    contains_album: list[str]
    album_field_start: int  # 1-based line of "contains_album = ["
    album_field_end: int    # 1-based line of closing "]"

    def get_field(self, name: str) -> str:
        if name == "contains_album":
            return " ".join(self.contains_album)
        return ""

    def set_field(self, name: str, value: str) -> None:
        if name == "contains_album":
            self.contains_album = value.split() if value.strip() else []


def _trip_sections(lines: list[str]) -> Iterator[_NumberedLines]:
    """Yield the body lines (with line numbers) for each [[trips]] block."""
    current: _NumberedLines = []
    in_trips = False

    for line_num, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped == "[[trips]]":
            if current:
                yield current
            current = []
            in_trips = True
        elif in_trips and stripped.startswith("[["):
            if current:
                yield current
            current = []
            in_trips = False
        elif in_trips:
            current.append((line_num, line))

    if current:
        yield current


def _parse_id(section: _NumberedLines) -> str | None:
    for _, line in section:
        if line.strip().startswith('id = "'):
            return line.strip()[6:].rstrip('"')
    return None


def _parse_album_array(section: _NumberedLines) -> tuple[list[str], int, int] | None:
    """Return (urns, start_line, end_line) for the contains_album field, or None."""
    in_array = False
    urns: list[str] = []
    start_line: int = 0

    for line_num, line in section:
        stripped = line.strip()
        if not in_array:
            if stripped.startswith("contains_album = ["):
                start_line = line_num
                in_array = True
                if stripped.endswith("]"):
                    return urns, start_line, line_num
        else:
            if stripped == "]":
                return urns, start_line, line_num
            elif stripped.startswith('"'):
                urns.append(stripped.strip('"').rstrip('",'))

    return None


def _parse_section(section: _NumberedLines) -> TripRow | None:
    trip_id = _parse_id(section)
    album_result = _parse_album_array(section)
    if trip_id is None or album_result is None:
        return None
    urns, start_line, end_line = album_result
    return TripRow(
        trip_id=trip_id,
        contains_album=urns,
        album_field_start=start_line,
        album_field_end=end_line,
    )


def load_trips() -> list[TripRow]:
    lines = THINGS_PATH.read_text(encoding="utf-8").splitlines()
    return [
        row
        for section in _trip_sections(lines)
        if (row := _parse_section(section)) is not None
    ]
