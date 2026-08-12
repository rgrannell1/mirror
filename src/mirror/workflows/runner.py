"""Run a zahir workflow: the job scope, the event log, and the progress bar.

Both the CLI and the individual command modules evaluate workflows through
here, so no command needs to import the CLI.
"""

from __future__ import annotations

import json
import os
import sys
from collections.abc import Generator, Iterable
from typing import Any

from bookman.bookman_types import Cumulative, Delta
from bookman.events import Event
from zahir import RootResult, evaluate, make_telemetry, setup, with_progress
from zahir.core.exceptions import JobError

from mirror.audit import audit_media
from mirror.workflows.copy.copy import copy_into_library, copy_open_nautilus, copy_workflow
from mirror.workflows.detect.detect import detect_pair, detect_subjects
from mirror.workflows.fetch.fetch import (
    fetch_copy_file,
    fetch_find_filtered,
    fetch_media_clustering,
    fetch_open_nautilus,
    fetch_photo_clustering,
    fetch_raw_clustering,
    fetch_resolve_dates,
    fetch_run_badger,
    fetch_workflow,
)
from mirror.workflows.free.free import (
    free_archive_file,
    free_archive_media,
    free_delete_file,
    free_verify_archive,
    free_workflow,
)
from mirror.workflows.output import workflow_output_message
from mirror.workflows.publish.publish import (
    publish_artifacts,
    publish_atom,
    publish_d1,
    publish_env,
    publish_stats,
    publish_triples,
    update_albums_markdown,
    update_photos_markdown,
    update_videos_markdown,
    write_metadata,
)
from mirror.workflows.scan.scan import (
    geonames_scan,
    media_scan,
    read_albums,
    read_photos,
    read_videos,
    scan_media,
    wikidata_scan,
)
from mirror.workflows.scan.taxonomy import chain_binomial, lookup_binomial, taxonomy_scan
from mirror.workflows.upload.upload import (
    compute_contrasting_grey,
    compute_image_mosaic,
    upload_media,
    upload_missing_photos,
    upload_missing_videos,
    upload_photo,
    upload_video,
    upload_video_thumbnail,
)
from mirror.workflows.website.website import (
    build_source,
    publish_d1_remote,
    publish_github,
    run_integration_tests,
)
from mirror.workflows.workflow import mirror_workflow

SCOPE = {
    "copy_workflow": copy_workflow,
    "copy_into_library": copy_into_library,
    "copy_open_nautilus": copy_open_nautilus,
    "fetch_workflow": fetch_workflow,
    "fetch_resolve_dates": fetch_resolve_dates,
    "fetch_find_filtered": fetch_find_filtered,
    "fetch_copy_file": fetch_copy_file,
    "fetch_run_badger": fetch_run_badger,
    "fetch_photo_clustering": fetch_photo_clustering,
    "fetch_media_clustering": fetch_media_clustering,
    "fetch_raw_clustering": fetch_raw_clustering,
    "fetch_open_nautilus": fetch_open_nautilus,
    "free_workflow": free_workflow,
    "free_archive_media": free_archive_media,
    "free_archive_file": free_archive_file,
    "free_verify_archive": free_verify_archive,
    "free_delete_file": free_delete_file,
    "mirror_workflow": mirror_workflow,
    "detect_subjects": detect_subjects,
    "detect_pair": detect_pair,
    "audit_media": audit_media,
    "scan_media": scan_media,
    "media_scan": media_scan,
    "geonames_scan": geonames_scan,
    "wikidata_scan": wikidata_scan,
    "taxonomy_scan": taxonomy_scan,
    "chain_binomial": chain_binomial,
    "lookup_binomial": lookup_binomial,
    "read_albums": read_albums,
    "read_photos": read_photos,
    "read_videos": read_videos,
    "compute_contrasting_grey": compute_contrasting_grey,
    "compute_image_mosaic": compute_image_mosaic,
    "upload_photo": upload_photo,
    "upload_missing_photos": upload_missing_photos,
    "upload_video_thumbnail": upload_video_thumbnail,
    "upload_video": upload_video,
    "upload_missing_videos": upload_missing_videos,
    "upload_media": upload_media,
    "publish_env": publish_env,
    "publish_atom": publish_atom,
    "publish_stats": publish_stats,
    "publish_triples": publish_triples,
    "publish_d1": publish_d1,
    "update_albums_markdown": update_albums_markdown,
    "update_photos_markdown": update_photos_markdown,
    "update_videos_markdown": update_videos_markdown,
    "write_metadata": write_metadata,
    "publish_artifacts": publish_artifacts,
    "build_source": build_source,
    "run_integration_tests": run_integration_tests,
    "publish_d1_remote": publish_d1_remote,
    "publish_github": publish_github,
}


def serialize_value(value: Any) -> Any:
    """Convert a bookman Primitive value to a JSON-serialisable form."""
    if value is None:
        return None
    if isinstance(value, (Delta, Cumulative)):
        return {"type": type(value).__name__, "value": value.value}
    return value


def event_to_dict(event: Event) -> dict:
    """Convert a bookman Event to a JSON-serialisable dict."""
    return {
        "at": event.at,
        "until": event.until,
        "dims": event.dims,
        "kind": event.kind,
        "value": serialize_value(event.value),
    }


def is_job_fail_end(event: Event) -> bool:
    """Return True if this event is a job_fail span end (carries the error message)."""
    dims = event.dims
    return "job_fail" in dims.get("tag", []) and "end" in dims.get("phase", [])


def record_events(events: Iterable[Any], path: str, error_path: str) -> Generator[Any, None, None]:
    """Wrap an event iterable, writing each bookman Event as a JSON line to path.

    Error events (job_fail) are additionally written as plain text to error_path.
    """
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as jsonl_fh, open(error_path, "w") as err_fh:
        for event in events:
            if isinstance(event, Event):
                jsonl_fh.write(json.dumps(event_to_dict(event)) + "\n")
                if is_job_fail_end(event) and event.value is not None:
                    fn = (event.dims.get("fn") or ["unknown"])[0]
                    err_fh.write(f"{fn}: {event.value}\n")
            yield event


def report_workflow_failure(err: JobError, error_path: str) -> None:
    """Print a concise failure report instead of an engine traceback."""
    print(f"\nworkflow failed: {err}", file=sys.stderr)
    print(f"failed job log: {error_path}", file=sys.stderr)
    raise SystemExit(1)


def stream_workflow_events(events: Iterable[Any], outputs: list[str]) -> Any:
    """Drain the event stream, collecting workflow output messages; return the root result."""
    root_result = None
    for event in events:
        if isinstance(event, RootResult):
            root_result = event.value
        elif isinstance(event, Event):
            message = workflow_output_message(event)
            if message:
                outputs.append(message)
    return root_result


def print_workflow_outputs(outputs: list[str]) -> None:
    """Print collected workflow messages once the progress bar has stopped."""
    for message in outputs:
        print(message, file=sys.stderr)


def run_workflow(
    root: str, workflow_input: dict, n_workers: int, log_paths: tuple[str, str]
) -> Any:
    """Evaluate a workflow root, streaming events to log files with a progress bar.

    Returns the root job's result, surfaced via RootResult on the event stream.
    """
    events = evaluate(
        setup(n_workers=n_workers),
        root,
        (workflow_input,),
        scope=SCOPE,
        handler_wrappers=[make_telemetry()],
    )
    root_result = None
    outputs: list[str] = []
    try:
        recorded = record_events(events, log_paths[0], log_paths[1])
        root_result = stream_workflow_events(with_progress(recorded), outputs)
    except JobError as err:
        print_workflow_outputs(outputs)
        report_workflow_failure(err, log_paths[1])
    print_workflow_outputs(outputs)
    return root_result
