"""Choose the oldest camera files to remove, and describe the result to the user."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from mirror.services.camera_storage import format_bytes, format_share
from mirror.services.camera_types import CameraFile, FreePlan, SpaceReport


def sort_key(media: CameraFile) -> tuple[float, str]:
    """Order files oldest first, breaking ties by path so runs are repeatable."""
    return (media.modified.timestamp(), media.relative)


def select_oldest_files(files: list[CameraFile], needed: int) -> tuple[CameraFile, ...]:
    """Take the oldest files, stopping once their combined size meets the budget."""
    if needed <= 0:
        return ()

    ordered = sorted(files, key=sort_key)
    selected: list[CameraFile] = []
    freed = 0

    for media in ordered:
        selected.append(media)
        freed += media.size
        if freed >= needed:
            break

    return tuple(selected)


def plan_bytes(files: tuple[CameraFile, ...]) -> int:
    """Return the combined size of the planned files."""
    return sum(media.size for media in files)


def plan_dates(files: tuple[CameraFile, ...]) -> tuple[date, date]:
    """Return the oldest and newest capture dates in the plan."""
    stamps = [media.modified.date() for media in files]
    return min(stamps), max(stamps)


def build_free_plan(
    files: list[CameraFile], space: SpaceReport, camera_dir: Path, needed: int
) -> FreePlan:
    """Build the plan for one run, without an archive path yet."""
    selected = select_oldest_files(files, needed)
    return FreePlan(files=selected, space=space, camera_dir=camera_dir, archive_path=None)


def with_archive_path(plan: FreePlan, archive_path: Path | None) -> FreePlan:
    """Return the plan again, naming the archive its files go into."""
    return FreePlan(
        files=plan.files,
        space=plan.space,
        camera_dir=plan.camera_dir,
        archive_path=archive_path,
    )


def space_lines(space: SpaceReport, camera_dir: Path) -> list[str]:
    """Describe the card's capacity, current free space, and target."""
    total = space.total_bytes
    return [
        f"camera:      {camera_dir}",
        f"capacity:    {format_bytes(total)}",
        f"free now:    {format_bytes(space.free_bytes)} ({format_share(space.free_bytes, total)})",
        f"target free: {format_bytes(space.target_free_bytes)}"
        f" ({format_share(space.target_free_bytes, total)})",
    ]


def removal_lines(plan: FreePlan) -> list[str]:
    """Describe what the run removes and where it goes."""
    freed = plan_bytes(plan.files)
    first, last = plan_dates(plan.files)
    destination = str(plan.archive_path) if plan.archive_path else "none (--no-preserve)"
    return [
        f"to remove:   {len(plan.files)} files, {format_bytes(freed)} ({first} .. {last})",
        f"archive:     {destination}",
    ]


def outcome_lines(plan: FreePlan) -> list[str]:
    """Describe the free space the run expects to leave, and any shortfall."""
    total = plan.space.total_bytes
    after = plan.space.free_bytes + plan_bytes(plan.files)
    lines = [f"free after:  {format_bytes(after)} ({format_share(after, total)})"]

    shortfall = plan.space.target_free_bytes - after
    if shortfall > 0:
        lines.append(
            f"shortfall:   {format_bytes(shortfall)} short of the target."
            " The camera holds no older media to remove."
        )
    return lines


def format_plan(plan: FreePlan) -> str:
    """Render the whole plan for the user to approve."""
    lines = ["mirror free — plan", *space_lines(plan.space, plan.camera_dir)]
    lines.extend(removal_lines(plan))
    lines.extend(outcome_lines(plan))
    return "\n".join(lines)
