"""Types for subject bounding-box detections."""

from typing import TypedDict


class DetectionBox(TypedDict):
    """One detected box, in original-image pixels."""

    coords: list[float]
    # box area in pixels, for ranking subjects by size
    volume: int
    confidence: float


class DetectionRequest(TypedDict):
    """Inputs for one subject detection request."""

    prompt: str
    threshold: float


class DetectionScan(TypedDict):
    """One completed scan of a photo-subject pair: its boxes and provenance."""

    boxes: list[DetectionBox]
    prompt: str
    threshold: float
    # pixel area of the image the boxes were measured on
    image_area: int


def box_volume(coords: list[float]) -> int:
    """Return the box area in pixels."""
    x1_coord, y1_coord, x2_coord, y2_coord = coords
    return round((x2_coord - x1_coord) * (y2_coord - y1_coord))
