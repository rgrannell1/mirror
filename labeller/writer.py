"""Write PhotoRow changes back to photos.md in-place."""

from pathlib import Path

from .parser import PhotoRow


def _row_to_line(row: PhotoRow) -> str:
    cells = [
        row.embedding,
        row.name,
        row.genre,
        row.rating,
        row.places,
        row.description,
        row.subjects,
        row.cover,
    ]
    return "| " + " | ".join(cells) + " |"


def save_row(path: Path, row: PhotoRow) -> None:
    with open(path) as handle:
        lines = handle.readlines()
    lines[row.line_number - 1] = _row_to_line(row) + "\n"
    with open(path, "w") as handle:
        handle.writelines(lines)
