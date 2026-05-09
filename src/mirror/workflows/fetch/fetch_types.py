"""Types for the fetch workflow."""

from datetime import date
from typing import TypedDict


class FetchInput(TypedDict):
    date_from: date
    date_to: date
    camera_dcim: str
    dest_dir: str


class BadgerProgress(TypedDict):
    photos_done: int
    photos_remaining: int
    videos_done: int
    videos_remaining: int
    raws_done: int
    raws_remaining: int
