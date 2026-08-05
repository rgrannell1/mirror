"""CLI entry for `mirror list-album`: list albums relative to a target date."""

from datetime import date

from mirror.commons.config import DATABASE_PATH
from mirror.services.database import SqliteDatabase


def parse_exif_date(exif_timestamp: str) -> date:
    """Convert an EXIF 'YYYY:MM:DD HH:MM:SS' timestamp to a date."""
    date_part = exif_timestamp.split(" ")[0]
    year, month, day = date_part.split(":")
    return date(int(year), int(month), int(day))


def classify_album(start: date, end: date, target: date) -> str:
    """Say whether an album's date range falls before, on, or after the target date."""
    if end < target:
        return "before"
    if start > target:
        return "after"
    return "on"


def run_list_album_command(date_str: str) -> int:
    """Print each album's title, start date, and position relative to the target date."""
    target = date.fromisoformat(date_str)

    with SqliteDatabase(DATABASE_PATH) as db:
        albums = list(db.album_data_view().list())

    rows = []
    for album in albums:
        if not album.min_date or not album.max_date:
            continue
        start = parse_exif_date(album.min_date)
        end = parse_exif_date(album.max_date)
        rows.append((album.name, start, classify_album(start, end, target)))

    rows.sort(key=lambda row: row[1])
    for name, start, position in rows:
        print(f"{name}\t{start.isoformat()}\t{position}")
    return 0
