"""Date formatting utilities for mirror."""

from datetime import datetime
from typing import Union


def date_range(
    min_date: Union[datetime, int, None],
    max_date: Union[datetime, int, None],
    short: bool = False,
) -> str:
    """
    Format a date range for display.

    Args:
        min_date: Start date as datetime or Unix timestamp in milliseconds
        max_date: End date as datetime or Unix timestamp in milliseconds
        short: If True, use abbreviated format (e.g., "22 - 24 Feb 2022")
               If False, use full format (e.g., "22 Feb 2022 — 24 Feb 2022")

    Returns:
        Formatted date range string

    Examples:
        >>> from datetime import datetime
        >>> d1 = datetime(2022, 2, 22)
        >>> d2 = datetime(2022, 2, 24)
        >>> date_range(d1, d2, short=True)
        '22 - 24 Feb 2022'
        >>> date_range(d1, d1, short=False)
        '22 Feb 2022'
    """
    if not min_date and not max_date:
        return "unknown date"

    # Parse dates - handle both datetime objects and Unix timestamps (in milliseconds)
    parsed_min_date: datetime
    parsed_max_date: datetime

    if isinstance(min_date, datetime):
        parsed_min_date = min_date
    elif isinstance(min_date, (int, float)):
        parsed_min_date = datetime.fromtimestamp(min_date / 1000)
    elif min_date is None:
        # If min_date is None but max_date exists, use max_date
        if isinstance(max_date, datetime):
            parsed_min_date = max_date
        elif isinstance(max_date, (int, float)):
            parsed_min_date = datetime.fromtimestamp(max_date / 1000)
        else:
            return "unknown date"
    else:
        return "unknown date"

    if isinstance(max_date, datetime):
        parsed_max_date = max_date
    elif isinstance(max_date, (int, float)):
        parsed_max_date = datetime.fromtimestamp(max_date / 1000)
    elif max_date is None:
        # If max_date is None, use min_date (which we know exists by now)
        parsed_max_date = parsed_min_date
    else:
        return "unknown date"

    if short:
        # Extract date components
        min_day = parsed_min_date.day
        max_day = parsed_max_date.day

        min_month = parsed_min_date.strftime("%b")
        max_month = parsed_max_date.strftime("%b")

        min_year = parsed_min_date.year
        max_year = parsed_max_date.year

        from_str = parsed_min_date.strftime(f"{min_day} %b")
        to_str = parsed_max_date.strftime(f"{max_day} %b")

        months_equal = min_month == max_month
        years_equal = min_year == max_year

        if from_str == to_str and years_equal:
            # e.g "22 Feb 2022"
            return f"{from_str} {min_year}"
        elif months_equal and years_equal:
            # e.g "22 - 24 Feb 2022"
            return f"{min_day} - {max_day} {max_month} {min_year}"
        else:
            # e.g "22 Feb 2022 - 24 Mar 2023"
            return f"{from_str} {min_year} - {to_str} {max_year}"
    else:
        # Full format
        from_str = parsed_min_date.strftime(f"{parsed_min_date.day} %b %Y")
        to_str = parsed_max_date.strftime(f"{parsed_max_date.day} %b %Y")

        if from_str == to_str:
            return from_str

        return f"{from_str} — {to_str}"
