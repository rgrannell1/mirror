"""Parse photos.md into structured PhotoRow objects."""

import re
from dataclasses import dataclass
from pathlib import Path

COLUMNS = ["embedding", "name", "genre", "rating", "places", "description", "subjects", "cover"]
EDITABLE_COLUMNS = ["name", "genre", "rating", "places", "description", "subjects", "cover"]

RATING_OPTIONS = ["⭐", "⭐⭐", "⭐⭐⭐", "⭐⭐⭐⭐", "⭐⭐⭐⭐⭐"]


@dataclass
class PhotoRow:
    line_number: int
    embedding: str
    thumbnail_url: str
    name: str
    genre: str
    rating: str
    places: str
    description: str
    subjects: str
    cover: str

    def get_field(self, field: str) -> str:
        return getattr(self, field)

    def set_field(self, field: str, value: str) -> None:
        setattr(self, field, value)


def _extract_url(embedding: str) -> str:
    match = re.search(r"!\[\]\(([^)]+)\)", embedding)
    return match.group(1) if match else embedding


def _parse_row(line: str, line_number: int) -> PhotoRow | None:
    parts = [part.strip() for part in line.split("|")]
    cells = parts[1:-1]
    if len(cells) != len(COLUMNS):
        return None
    embedding = cells[0]
    return PhotoRow(
        line_number=line_number,
        embedding=embedding,
        thumbnail_url=_extract_url(embedding),
        name=cells[1],
        genre=cells[2],
        rating=cells[3],
        places=cells[4],
        description=cells[5],
        subjects=cells[6],
        cover=cells[7],
    )


def load_photos(path: Path) -> list[PhotoRow]:
    rows = []
    with open(path) as f:
        lines = f.readlines()
    for i, line in enumerate(lines, 1):
        stripped = line.rstrip("\n")
        if not stripped.startswith("|") or "---" in stripped or stripped.startswith("| embedding"):
            continue
        row = _parse_row(stripped, i)
        if row is not None:
            rows.append(row)
    return rows
