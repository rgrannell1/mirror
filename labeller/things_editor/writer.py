"""Write TripRow changes back to things.toml in-place."""

from labeller.things.loader import THINGS_PATH
from labeller.things.trips import TripRow


def _album_array_lines(urns: list[str]) -> list[str]:
    return [
        "contains_album = [\n",
        *[f'    "{urn}",\n' for urn in urns],
        "]\n",
    ]


def save_trip_row(row: TripRow) -> None:
    lines = THINGS_PATH.read_text(encoding="utf-8").splitlines(keepends=True)
    replacement = _album_array_lines(row.contains_album)
    start = row.album_field_start - 1  # to 0-based
    end = row.album_field_end          # exclusive upper bound
    lines[start:end] = replacement
    THINGS_PATH.write_text("".join(lines), encoding="utf-8")
