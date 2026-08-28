"""Date formatting utilities for mirror."""

from datetime import datetime
from typing import Union


def parse_flexible_date(value: Union[datetime, int, float, None]) -> datetime | None:
    """Coerce a datetime or millisecond Unix timestamp into a datetime."""
    if isinstance(value, datetime):
        return value

    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value / 1000)

    return None


def short_date_range(min_dt: datetime, max_dt: datetime) -> str:
    """Abbreviated range, collapsing a shared month and year."""
    from_str = min_dt.strftime(f"{min_dt.day} %b")
    to_str = max_dt.strftime(f"{max_dt.day} %b")

    months_equal = min_dt.strftime("%b") == max_dt.strftime("%b")
    years_equal = min_dt.year == max_dt.year

    if from_str == to_str and years_equal:
        # e.g "22 Feb 2022"
        return f"{from_str} {min_dt.year}"

    if months_equal and years_equal:
        # e.g "22 - 24 Feb 2022"
        return f"{min_dt.day} - {max_dt.day} {max_dt.strftime('%b')} {min_dt.year}"

    # e.g "22 Feb 2022 - 24 Mar 2023"
    return f"{from_str} {min_dt.year} - {to_str} {max_dt.year}"


def full_date_range(min_dt: datetime, max_dt: datetime) -> str:
    """Full-format range, collapsing equal endpoints."""
    from_str = min_dt.strftime(f"{min_dt.day} %b %Y")
    to_str = max_dt.strftime(f"{max_dt.day} %b %Y")

    if from_str == to_str:
        return from_str

    return f"{from_str} — {to_str}"


def resolve_date_range(
    min_date: Union[datetime, int, None],
    max_date: Union[datetime, int, None],
) -> tuple[datetime | None, datetime | None]:
    """Resolve missing date endpoints from the available endpoint."""
    # Either endpoint falls back to the other when missing
    parsed_min_date = parse_flexible_date(min_date) or parse_flexible_date(max_date)
    parsed_max_date = parse_flexible_date(max_date) or parsed_min_date
    return parsed_min_date, parsed_max_date


def date_range(
    min_date: Union[datetime, int, None],
    max_date: Union[datetime, int, None],
    short: bool = False,
) -> str:
    """Format a full or abbreviated date range for display."""
    parsed_min_date, parsed_max_date = resolve_date_range(min_date, max_date)

    if parsed_min_date is None or parsed_max_date is None:
        return "unknown date"

    if short:
        return short_date_range(parsed_min_date, parsed_max_date)

    return full_date_range(parsed_min_date, parsed_max_date)
