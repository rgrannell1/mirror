import argparse
import json
import logging
import multiprocessing
import os
import sys
from collections.abc import Generator, Iterable
from typing import Any

from bookman.bookman_types import Cumulative, Delta
from bookman.events import Event
from zahir import RootResult, evaluate, make_telemetry, setup, with_progress
from zahir.core.exceptions import JobError

from mirror.audit import audit_media, run_audit_command
from mirror.commons import config
from mirror.commons.config import (
    MIRROR_ERROR_PATH,
    MIRROR_JSONL_PATH,
    ZAHIR_JSONL_PATH,
    ZAHIR_STDERR_PATH,
)
from mirror.list_album import run_list_album_command
from mirror.workflows.copy.copy import copy_into_library, copy_open_nautilus, copy_workflow
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

logging.basicConfig(level=logging.INFO, force=True)
logging.getLogger("PIL").setLevel(logging.WARNING)

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
    "mirror_workflow": mirror_workflow,
    "audit_media": audit_media,
    "scan_media": scan_media,
    "media_scan": media_scan,
    "geonames_scan": geonames_scan,
    "wikidata_scan": wikidata_scan,
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


def add_pipeline_flags(parser: argparse.ArgumentParser) -> None:
    """Add the full-pipeline flags to the top-level parser."""

    parser.add_argument("--no-upload-images", dest="upload_images", action="store_false")
    parser.add_argument("--no-upload-videos", dest="upload_videos", action="store_false")
    parser.add_argument("--force-recompute-grey", action="store_true")
    parser.add_argument("--force-recompute-mosaic", action="store_true")
    parser.add_argument("--force-upload-images", action="store_true")
    parser.add_argument("--force-upload-videos", action="store_true")
    parser.add_argument("--force-roles", nargs="+", default=None, metavar="ROLE")
    parser.add_argument("--publish-d1", action="store_true")


def add_subcommands(parser: argparse.ArgumentParser) -> None:
    """Add the copy, audit, and fetch subcommands to the parser."""

    subparsers = parser.add_subparsers(dest="command")

    copy_parser = subparsers.add_parser(
        "copy", help="Copy a recent raw import into the managed library"
    )
    copy_parser.add_argument(
        "-n",
        dest="nth",
        type=int,
        default=1,
        metavar="N",
        help="Nth most recent import (default: 1)",
    )

    subparsers.add_parser("audit", help="Report reasons publication will fail (read-only)")

    list_album_parser = subparsers.add_parser(
        "list-album", help="List albums before, on, or after a date"
    )
    list_album_parser.add_argument(
        "--date",
        dest="date",
        required=True,
        metavar="YYYY-MM-DD",
        help="Target date, e.g. 2026-05-09",
    )

    fetch_parser = subparsers.add_parser("fetch", help="Import media from a connected camera")
    fetch_parser.add_argument(
        "--from",
        dest="date_from",
        required=True,
        metavar="DATE",
        help='Start date, e.g. "today" or "two days ago"',
    )
    fetch_parser.add_argument(
        "--to",
        dest="date_to",
        default="today",
        metavar="DATE",
        help='End date, e.g. "today" or "2026-05-09" (default: today)',
    )
    fetch_parser.add_argument(
        "--camera",
        dest="camera",
        default=config.CAMERA_DCIM_DEFAULT,
        metavar="PATH",
        help="Path to camera DCIM directory",
    )


def build_parser() -> argparse.ArgumentParser:
    """Construct the mirror argument parser with its subcommands."""

    parser = argparse.ArgumentParser(description="Mirror media pipeline")
    add_pipeline_flags(parser)
    add_subcommands(parser)
    return parser


def report_workflow_failure(err: JobError, error_path: str) -> None:
    """Print a concise failure report instead of an engine traceback."""
    print(f"\nworkflow failed: {err}", file=sys.stderr)
    print(f"failed job log: {error_path}", file=sys.stderr)
    raise SystemExit(1)


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
    try:
        for event in with_progress(record_events(events, log_paths[0], log_paths[1])):
            if isinstance(event, RootResult):
                root_result = event.value
    except JobError as err:
        report_workflow_failure(err, log_paths[1])
    return root_result


def run_copy_command(args: argparse.Namespace) -> None:
    """Prompt for an album title and run the copy workflow."""

    title = input("Album title: ").strip()
    if not title:
        raise SystemExit("Album title is required")

    copy_input = {"title": title, "nth": args.nth}
    run_workflow("copy_workflow", copy_input, 4, (ZAHIR_JSONL_PATH, ZAHIR_STDERR_PATH))


def run_fetch_command(args: argparse.Namespace) -> None:
    """Run the camera fetch workflow."""

    fetch_input = {"from_str": args.date_from, "to_str": args.date_to, "camera": args.camera}
    run_workflow("fetch_workflow", fetch_input, 15, (ZAHIR_JSONL_PATH, ZAHIR_STDERR_PATH))


def run_pipeline_command(args: argparse.Namespace) -> None:
    """Run the full mirror pipeline workflow."""

    if multiprocessing.get_start_method() != "fork":
        multiprocessing.set_start_method("fork", force=True)

    workflow_input = {
        "upload_images": args.upload_images,
        "upload_videos": args.upload_videos,
        "force_recompute_grey": args.force_recompute_grey,
        "force_recompute_mosaic": args.force_recompute_mosaic,
        "force_upload_images": args.force_upload_images,
        "force_upload_videos": args.force_upload_videos,
        "force_roles": args.force_roles,
        "publish_d1": args.publish_d1,
    }
    log_paths = (MIRROR_JSONL_PATH, MIRROR_ERROR_PATH)
    summary = run_workflow("mirror_workflow", workflow_input, 15, log_paths)
    if summary:
        print(summary)


def main():
    """Execute the mirror media pipeline"""

    args = build_parser().parse_args()

    if args.command == "copy":
        run_copy_command(args)
        return

    if args.command == "audit":
        raise SystemExit(run_audit_command())

    if args.command == "list-album":
        raise SystemExit(run_list_album_command(args.date))

    if args.command == "fetch":
        run_fetch_command(args)
        return

    run_pipeline_command(args)
