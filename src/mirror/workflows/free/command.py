"""CLI entry for `mirror free`: plan and approve, then run the free workflow.

The plan and the y/n prompt stay outside the workflow. Zahir jobs must not
print, and none of the planning work is worth a job.
"""

from __future__ import annotations

import sys
import tarfile
from pathlib import Path

from mirror.commons.config import ARCHIVED_PHOTOS_DIRECTORY, ZAHIR_JSONL_PATH, ZAHIR_STDERR_PATH
from mirror.workflows.free.archive import build_archive_path
from mirror.workflows.free.free_types import FreePlan
from mirror.workflows.free.plan import build_free_plan, format_plan, plan_dates, with_archive_path
from mirror.workflows.free.storage import (
    bytes_needed,
    format_bytes,
    format_share,
    list_camera_files,
    read_space,
    resolve_camera_dir,
    to_entry,
)
from mirror.workflows.free.validate import parse_percentage
from mirror.workflows.runner import run_workflow

# Answers accepted at the plan prompt. Anything else cancels the run.
APPROVALS = ("y", "yes")

# Workers given to the free workflow. Deletes fan out; archiving is one stream.
FREE_WORKERS = 8


def build_run_plan(camera: str, percent: float, no_preserve: bool) -> FreePlan | None:
    """Plan one run, or return None when the card already has enough free space."""
    camera_dir = resolve_camera_dir(camera)
    space = read_space(camera_dir, percent)
    needed = bytes_needed(space)
    if needed == 0:
        return None

    files = list_camera_files(camera_dir)
    if not files:
        raise FileNotFoundError(f"No media found on {camera_dir}")

    plan = build_free_plan(files, space, camera_dir, needed)
    if no_preserve:
        return plan

    first, last = plan_dates(plan.files)
    archive_path = build_archive_path(Path(ARCHIVED_PHOTOS_DIRECTORY), first, last)
    return with_archive_path(plan, archive_path)


def approve(assume_yes: bool) -> bool:
    """Ask the user to approve the plan, unless --yes already did."""
    if assume_yes:
        return True
    return input("Proceed? [y/N] ").strip().lower() in APPROVALS


def run_free_workflow(plan: FreePlan) -> dict:
    """Hand the approved plan to the zahir workflow, which reports its own progress."""
    archive_path = str(plan.archive_path) if plan.archive_path else None
    workflow_input = {
        "files": [to_entry(media) for media in plan.files],
        "archive_path": archive_path,
    }
    log_paths = (ZAHIR_JSONL_PATH, ZAHIR_STDERR_PATH)
    return run_workflow("free_workflow", workflow_input, FREE_WORKERS, log_paths)


def report_result(plan: FreePlan, percent: float) -> None:
    """Print the free space the run left on the card."""
    space = read_space(plan.camera_dir, percent)
    share = format_share(space.free_bytes, space.total_bytes)
    print(f"free now: {format_bytes(space.free_bytes)} ({share})")


def free_camera_space(percent_raw: str, no_preserve: bool, assume_yes: bool, camera: str) -> int:
    """Run the whole flow: plan, approve, then archive, verify, and delete."""
    percent = parse_percentage(percent_raw)

    plan = build_run_plan(camera, percent, no_preserve)
    if plan is None:
        print(f"camera already has at least {percent:g}% free. Nothing to do")
        return 0

    print(format_plan(plan))
    if not approve(assume_yes):
        print("aborted. Nothing was deleted")
        return 0

    run_free_workflow(plan)
    report_result(plan, percent)
    return 0


def run_free_command(percent_raw: str, no_preserve: bool, assume_yes: bool, camera: str) -> int:
    """Report a failure as a plain message instead of a traceback."""
    try:
        return free_camera_space(percent_raw, no_preserve, assume_yes, camera)
    except (ValueError, OSError, RuntimeError, tarfile.TarError) as err:
        print(f"mirror free: {err}", file=sys.stderr)
        return 1
