"""Parse albums.md into structured AlbumRow objects."""

import re
from dataclasses import dataclass
from pathlib import Path

COLUMNS = ["embedding", "title", "permalink", "country", "summary"]
EDITABLE_COLUMNS = ["title", "permalink", "country", "summary"]


@dataclass
class AlbumRow:
    line_number: int
    embedding: str
    thumbnail_url: str
    title: str
    permalink: str
    country: str
    summary: str

    def get_field(self, field: str) -> str:
        return getattr(self, field)

    def set_field(self, field: str, value: str) -> None:
        setattr(self, field, value)


def _extract_url(embedding: str) -> str:
    match = re.search(r"!\[\]\(([^)]+)\)", embedding)
    return match.group(1) if match else embedding


def _parse_row(line: str, line_number: int) -> AlbumRow | None:
    parts = [part.strip() for part in line.split("|")]
    cells = parts[1:-1]
    if len(cells) != len(COLUMNS):
        return None
    embedding = cells[0]
    return AlbumRow(
        line_number=line_number,
        embedding=embedding,
        thumbnail_url=_extract_url(embedding),
        title=cells[1],
        permalink=cells[2],
        country=cells[3],
        summary=cells[4],
    )


def load_albums(path: Path) -> list[AlbumRow]:
    rows = []
    with open(path) as handle:
        lines = handle.readlines()
    for line_number, line in enumerate(lines, 1):
        stripped = line.rstrip("\n")
        if not stripped.startswith("|") or "---" in stripped or stripped.startswith("| embedding"):
            continue
        row = _parse_row(stripped, line_number)
        if row is not None:
            rows.append(row)
    return rows
