"""Typed shapes for image/video encoding option dicts."""

from __future__ import annotations

from typing import NotRequired, Required, TypedDict


class ImageEncodingParams(TypedDict, total=False):
    format: Required[str]
    quality: NotRequired[int]
    method: NotRequired[int]
    width: NotRequired[int]
    height: NotRequired[int]
    lossless: NotRequired[bool]


class VideoEncodingParams(TypedDict):
    bitrate: str
    width: int | None
    height: int | None
