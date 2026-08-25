"""Detect subject bounding boxes for photos and store them in the database."""

import sqlite3
from collections.abc import Generator
from typing import Any

from zahir import JobContext, await_all, concurrency_dependency, resource_dependency

from mirror.commons.config import DATABASE_PATH
from mirror.commons.constants import (
    DETECTION_CONCURRENCY_LIMIT,
    DETECTION_CONFIDENCE_THRESHOLD,
    DETECTION_CPU_MAX_PERCENT,
    DETECTION_MEMORY_MAX_PERCENT,
)
from mirror.data.things import thing_names
from mirror.models.detection import DetectionScan
from mirror.services.database import SqliteDatabase
from mirror.workflows.detect.utils import list_missing_detections
from mirror.workflows.output import workflow_output


def store_scan(pair: dict, scan: DetectionScan) -> Generator[Any, Any, bool]:
    """Store one scan row; report database failures instead of raising them."""
    try:
        with SqliteDatabase(DATABASE_PATH) as db:
            db.subject_detections_table().add(pair["phash"], pair["subject_type"], scan)
    except sqlite3.Error as err:
        yield workflow_output(f"storing detection failed for {pair['fpath']}: {err}")
        return False

    return True


def detect_and_store(input: dict) -> Generator[Any, Any, bool]:
    """Detect boxes for one pair and store them with the prompt used."""
    # imported here: the detector pulls in torch, which is too slow for CLI start-up
    from mirror.services.detector import build_prompt, detect_boxes  # noqa: PLC0415

    fpath = input["fpath"]
    subject_type = input["subject_type"]
    prompt = build_prompt(subject_type, tuple(input["names"]))
    threshold = DETECTION_CONFIDENCE_THRESHOLD
    try:
        boxes, image_area = detect_boxes(fpath, prompt, threshold)
    except Exception as err:  # noqa: BLE001
        yield workflow_output(f"detection failed for {fpath} ({subject_type}): {err}")
        return False

    scan: DetectionScan = {
        "boxes": boxes,
        "prompt": prompt,
        "threshold": threshold,
        "image_area": image_area,
    }
    stored = yield from store_scan(input, scan)
    return stored


def detect_pair(ctx: JobContext, input: dict) -> Generator[Any, Any, dict]:
    """Find and store boxes for one photo-subject pair, gated on system resources.

    The concurrency slot caps simultaneous detections; the resource gates hold
    the job until CPU and memory are under their limits, so the engine paces the
    fan-out. Failures are reported, not raised, so one bad photo cannot fail the
    whole await_all.
    """
    yield from concurrency_dependency("subject_detection", limit=DETECTION_CONCURRENCY_LIMIT)
    yield from resource_dependency("cpu", max_percent=DETECTION_CPU_MAX_PERCENT)
    yield from resource_dependency("memory", max_percent=DETECTION_MEMORY_MAX_PERCENT)

    stored = yield from detect_and_store(input)
    return {"stored": stored}
    yield


def detect_subjects(ctx: JobContext, input: dict) -> Generator[Any, Any, dict]:
    """Find and store bounding boxes for each photo-subject pair without a row.

    One sub-job per pair; zahir balances them against the resource limits.
    Idempotent: pairs with a stored row (even an empty one) are skipped, so a
    stopped run resumes where it left off.
    """
    with SqliteDatabase(DATABASE_PATH) as db:
        pairs = list(list_missing_detections(db, thing_names()))

    jobs = [
        ctx.scope.detect_pair({
            "phash": phash,
            "subject_type": subject_type,
            "fpath": fpath,
            "names": list(names),
        })
        for phash, subject_type, fpath, names in pairs
    ]
    results = yield await_all(jobs)

    detected = sum(1 for result in results if result["stored"])
    failed = len(results) - detected

    if pairs:
        yield workflow_output(f"subject detection: {detected} scanned, {failed} failed")

    return {"detected": detected, "failed": failed}
    yield
