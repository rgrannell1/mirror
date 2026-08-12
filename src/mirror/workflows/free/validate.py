"""Input validation for `mirror free`."""

from __future__ import annotations

from mirror.commons.constants import MAX_FREE_PERCENT


def parse_percentage(raw: str) -> float:
    """Read a '10%' or '10' argument as a percentage, rejecting out-of-range values."""
    text = raw.strip().removesuffix("%").strip()

    try:
        percent = float(text)
    except ValueError:
        raise ValueError(f"Not a percentage: {raw!r}") from None

    if percent <= 0:
        raise ValueError(f"Percentage must be above zero: {raw!r}")

    if percent > MAX_FREE_PERCENT:
        raise ValueError(f"Percentage must be at most {MAX_FREE_PERCENT:g}%: {raw!r}")

    return percent
