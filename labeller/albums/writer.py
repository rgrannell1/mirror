"""Write AlbumRow changes back to albums.md in-place."""

from pathlib import Path

from .parser import AlbumRow


def _row_to_line(row: AlbumRow) -> str:
    cells = [
        row.embedding,
        row.title,
        row.permalink,
        row.country,
        row.summary,
    ]
    return "| " + " | ".join(cells) + " |"


def save_album_row(path: Path, row: AlbumRow) -> None:
    with open(path) as handle:
        lines = handle.readlines()
    lines[row.line_number - 1] = _row_to_line(row) + "\n"
    with open(path, "w") as handle:
        handle.writelines(lines)
