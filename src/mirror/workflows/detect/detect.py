"""Detect subject bounding boxes for photos and store them in the database."""

from collections.abc import Generator
from typing import Any

from zahir import JobContext, await_all, concurrency_dependency, resource_dependency

from mirror.commons.constants import (
    DETECTION_CONCURRENCY_LIMIT,
    DETECTION_CPU_MAX_PERCENT,
    DETECTION_MEMORY_MAX_PERCENT,
)
from mirror.services.detection_scan import (
    DetectionStoreError,
    detect_scan,
    list_pending_detections,
    store_detection,
)
from mirror.workflows.output import workflow_output


def detect_and_store(input: dict) -> Generator[Any, Any, bool]:
    """Detect boxes for one pair and store them with the prompt used."""
    fpath = input["fpath"]
    subject_type = input["subject_type"]
    try:
        scan = detect_scan(input)
    except Exception as err:  # noqa: BLE001
        yield workflow_output(f"detection failed for {fpath} ({subject_type}): {err}")
        return False

    try:
        store_detection(input, scan)
    except DetectionStoreError as err:
        yield workflow_output(f"storing detection failed for {fpath}: {err}")
        return False
    return True


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
    pairs = list_pending_detections()

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
