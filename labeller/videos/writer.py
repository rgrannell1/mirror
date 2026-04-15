"""Write VideoRow changes back to videos.md in-place."""

from pathlib import Path

from .parser import VideoRow


def _row_to_line(row: VideoRow) -> str:
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


def save_video_row(path: Path, row: VideoRow) -> None:
    with open(path) as handle:
        lines = handle.readlines()
    lines[row.line_number - 1] = _row_to_line(row) + "\n"
    with open(path, "w") as handle:
        handle.writelines(lines)
