"""Command line entry point: parse arguments and dispatch to a command."""

import argparse
import logging
import multiprocessing
from typing import Any

from mirror.audit import run_audit_command
from mirror.commons import config
from mirror.commons.config import (
    MIRROR_ERROR_PATH,
    MIRROR_JSONL_PATH,
    ZAHIR_JSONL_PATH,
    ZAHIR_STDERR_PATH,
)
from mirror.commons.constants import MAX_FREE_PERCENT
from mirror.list_album import run_list_album_command
from mirror.services.camera_storage import detect_camera_dir
from mirror.workflows.free import run_free_command
from mirror.workflows.runner import run_workflow

logging.basicConfig(level=logging.INFO, force=True)
logging.getLogger("PIL").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)


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
    parser.add_argument("--no-github", dest="no_github", action="store_true")


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
        help="Path to camera DCIM directory; default: detect one removable card",
    )

    add_free_subcommand(subparsers)


def add_free_subcommand(subparsers: Any) -> None:
    """Add the free subcommand, which clears the oldest media off the camera."""

    free_parser = subparsers.add_parser(
        "free", help="Archive and remove the oldest camera media to free space"
    )
    free_parser.add_argument(
        "percent",
        metavar="PERCENT",
        help=f"Free space to leave on the card, e.g. 10%% (max {MAX_FREE_PERCENT:g}%%)",
    )
    free_parser.add_argument(
        "--no-preserve",
        dest="no_preserve",
        action="store_true",
        help="Delete the media instead of archiving it first",
    )
    free_parser.add_argument(
        "--yes",
        dest="assume_yes",
        action="store_true",
        help="Skip the approval prompt",
    )
    free_parser.add_argument(
        "--camera",
        dest="camera",
        default=None,
        metavar="PATH",
        help="Path to camera DCIM directory; default: detect one removable card",
    )


def build_parser() -> argparse.ArgumentParser:
    """Construct the mirror argument parser with its subcommands."""

    parser = argparse.ArgumentParser(description="Mirror media pipeline")
    add_pipeline_flags(parser)
    add_subcommands(parser)
    return parser


def run_copy_command(args: argparse.Namespace) -> None:
    """Prompt for an album title and run the copy workflow."""

    title = input("Album title: ").strip()
    if not title:
        raise SystemExit("Album title is required")

    copy_input = {"title": title, "nth": args.nth}
    run_workflow("copy_workflow", copy_input, 4, (ZAHIR_JSONL_PATH, ZAHIR_STDERR_PATH))


def run_fetch_command(args: argparse.Namespace) -> None:
    """Run the camera fetch workflow."""

    camera = args.camera if args.camera is not None else str(detect_camera_dir())
    fetch_input = {"from_str": args.date_from, "to_str": args.date_to, "camera": camera}
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
        "no_github": args.no_github,
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

    if args.command == "free":
        raise SystemExit(
            run_free_command(args.percent, args.no_preserve, args.assume_yes, args.camera)
        )

    run_pipeline_command(args)
