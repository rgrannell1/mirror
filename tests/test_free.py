"""Tests for `mirror free`: selection, archive verification, and the zahir workflow."""

import os
import tarfile
from datetime import date, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest
from zahir.core.commons.constants import DependencyState
from zahir.core.effects import EAcquire, EAwait, EGetState, ESetState
from zahir.core.scope_proxy import ScopeProxy

from mirror.workflows.free.archive import (
    PARTIAL_SUFFIX,
    build_archive_path,
    find_unverified,
    partial_path,
    read_archive_sizes,
    write_archive,
)
from mirror.workflows.free.command import build_run_plan
from mirror.workflows.free.free import (
    free_archive_file,
    free_archive_media,
    free_delete_file,
    free_verify_archive,
    free_workflow,
    summarise_deletes,
)
from mirror.workflows.free.free_types import CameraFile, SpaceReport
from mirror.workflows.free.plan import plan_bytes, plan_dates, select_oldest_files
from mirror.workflows.free.storage import (
    bytes_needed,
    detect_camera_dir,
    format_bytes,
    is_removable_device,
    list_camera_files,
    require_removable_device,
    resolve_camera_dir,
    to_entry,
)
from mirror.workflows.free.validate import parse_percentage

FREE_SCOPE = {
    "free_workflow": free_workflow,
    "free_archive_media": free_archive_media,
    "free_archive_file": free_archive_file,
    "free_verify_archive": free_verify_archive,
    "free_delete_file": free_delete_file,
}


class FakeContext:
    """Stands in for JobContext, exposing only the job scope."""

    def __init__(self, scope: dict) -> None:
        self.scope = ScopeProxy(scope)


def fake_result(spec) -> dict:
    """Answer one dispatched job with a result matching its input."""
    if spec.fn_name == "free_delete_file":
        return {"freed": spec.args[0]["size"], "error": None}
    return {}


def is_card_device(device: str) -> bool:
    """Treat the test card device as removable."""
    return device == "/dev/sde1"


def is_fixed_device(device: str) -> bool:
    """Treat every test device as fixed storage."""
    return False


def allow_test_camera(camera_dir: Path) -> None:
    """Allow a temporary directory to stand in for removable storage."""


def answer_effect(effect, dispatched: list, signalled: list):
    """Answer one effect: record dispatches, grant dependencies, and note progress signals."""
    if isinstance(effect, EAwait):
        dispatched.extend(spec.fn_name for spec in effect.jobs)
        results = [fake_result(spec) for spec in effect.jobs]
        return results[0] if effect.scalar else results
    if isinstance(effect, EAcquire):
        return True
    if isinstance(effect, EGetState):
        return DependencyState.SATISFIED
    if isinstance(effect, ESetState):
        signalled.append(effect.name)
    return None


def drive_job(generator, dispatched: list | None = None, signalled: list | None = None):
    """Run a job generator to completion, answering effects by type rather than by position."""
    dispatched = dispatched if dispatched is not None else []
    signalled = signalled if signalled is not None else []
    try:
        effect = generator.send(None)
        while True:
            effect = generator.send(answer_effect(effect, dispatched, signalled))
    except StopIteration as stop:
        return stop.value


def make_camera_file(name: str, size: int, day: int) -> CameraFile:
    """Build a CameraFile with no file behind it, for selection tests."""
    return CameraFile(
        path=Path(f"/camera/{name}"),
        relative=name,
        size=size,
        modified=datetime(2026, 5, day),
    )


def write_media(camera_dir: Path, name: str, size: int, day: int) -> Path:
    """Write one fake media file of a given size and modification day."""
    path = camera_dir / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"x" * size)
    stamp = datetime(2026, 5, day).timestamp()
    os.utime(path, (stamp, stamp))
    return path


def test_parse_percentage_accepts_valid_input():
    """Proves a percentage argument is read with or without its percent sign."""
    cases = [("10%", 10.0), ("10", 10.0), (" 2.5 % ", 2.5), ("30%", 30.0)]

    for raw, expected in cases:
        assert parse_percentage(raw) == expected


def test_parse_percentage_rejects_invalid_input():
    """Proves the command refuses percentages that are unreadable, zero, or above the cap."""
    cases = ["", "abc", "0", "-5%", "31%", "100%"]

    for raw in cases:
        with pytest.raises(ValueError):
            parse_percentage(raw)


def test_bytes_needed_reports_the_shortfall():
    """Proves the byte budget is the gap between current and target free space."""
    cases = [(100, 10, 30, 20), (100, 30, 30, 0), (100, 50, 30, 0)]

    for total, free, target, expected in cases:
        space = SpaceReport(total_bytes=total, free_bytes=free, target_free_bytes=target)
        assert bytes_needed(space) == expected


def test_select_oldest_files_takes_the_oldest_until_the_budget_is_met():
    """Proves selection runs oldest first and stops as soon as the budget is covered."""
    files = [
        make_camera_file("newest.jpg", 100, 3),
        make_camera_file("oldest.jpg", 100, 1),
        make_camera_file("middle.jpg", 100, 2),
    ]

    cases = [(1, ["oldest.jpg"]), (150, ["oldest.jpg", "middle.jpg"]), (0, [])]

    for needed, expected in cases:
        selected = select_oldest_files(files, needed)
        assert [media.relative for media in selected] == expected


def test_select_oldest_files_stops_when_the_camera_runs_out():
    """Proves an impossible budget takes every file rather than looping or failing."""
    files = [make_camera_file("a.jpg", 10, 1), make_camera_file("b.jpg", 10, 2)]

    selected = select_oldest_files(files, 1000)

    assert len(selected) == 2
    assert plan_bytes(selected) == 20


def test_plan_dates_span_the_selection():
    """Proves the plan reports the oldest and newest capture dates it covers."""
    files = (make_camera_file("a.jpg", 10, 4), make_camera_file("b.jpg", 10, 9))

    assert plan_dates(files) == (date(2026, 5, 4), date(2026, 5, 9))


def test_resolve_camera_dir_complains_when_not_mounted(tmp_path):
    """Proves an absent camera path fails loudly instead of doing nothing."""
    with pytest.raises(FileNotFoundError):
        resolve_camera_dir(str(tmp_path / "absent"))


def test_is_removable_device_reads_the_parent_disk_flag(tmp_path):
    """Proves a partition inherits the removable flag from its parent disk."""
    disk_dir = tmp_path / "devices" / "sde"
    partition_dir = disk_dir / "sde1"
    partition_dir.mkdir(parents=True)
    (disk_dir / "removable").write_text("1\n")
    (tmp_path / "sde1").symlink_to(partition_dir)

    assert is_removable_device("/dev/sde1", tmp_path)


def test_detect_camera_dir_finds_the_only_removable_card(tmp_path, monkeypatch):
    """Proves automatic detection ignores a DCIM directory on a fixed disk."""
    fixed_mount = tmp_path / "fixed"
    card_mount = tmp_path / "card"
    (fixed_mount / "DCIM").mkdir(parents=True)
    (card_mount / "DCIM").mkdir(parents=True)
    partitions = [
        SimpleNamespace(device="/dev/nvme0n1p2", mountpoint=str(fixed_mount)),
        SimpleNamespace(device="/dev/sde1", mountpoint=str(card_mount)),
    ]
    monkeypatch.setattr(
        "mirror.workflows.free.storage.is_removable_device",
        is_card_device,
    )

    assert detect_camera_dir(partitions) == card_mount / "DCIM"


def test_require_removable_device_refuses_a_fixed_disk(tmp_path, monkeypatch):
    """Proves an explicit camera path cannot point into the system disk."""
    camera_dir = tmp_path / "DCIM"
    camera_dir.mkdir()
    partitions = [SimpleNamespace(device="/dev/nvme0n1p2", mountpoint=str(tmp_path))]
    monkeypatch.setattr("mirror.workflows.free.storage.is_removable_device", is_fixed_device)

    with pytest.raises(PermissionError, match="non-removable"):
        require_removable_device(camera_dir, partitions)


def test_list_camera_files_finds_media_in_subfolders(tmp_path):
    """Proves media is found recursively and non-media files are ignored."""
    write_media(tmp_path, "100_PANA/P1000001.JPG", 10, 1)
    write_media(tmp_path, "100_PANA/P1000001.RW2", 20, 1)
    write_media(tmp_path, "101_PANA/CLIP.MP4", 30, 2)
    write_media(tmp_path, "100_PANA/INDEX.CTG", 40, 1)

    found = list_camera_files(tmp_path)

    assert sorted(media.relative for media in found) == [
        "100_PANA/P1000001.JPG",
        "100_PANA/P1000001.RW2",
        "101_PANA/CLIP.MP4",
    ]


def test_archive_roundtrip_verifies_every_file(tmp_path):
    """Proves an archive holding every file at the right size reports no failures."""
    camera_dir = tmp_path / "DCIM"
    write_media(camera_dir, "100_PANA/A.JPG", 64, 1)
    write_media(camera_dir, "101_PANA/B.JPG", 32, 2)
    files = tuple(list_camera_files(camera_dir))

    archive_path = tmp_path / "archive.tar.gz"
    list(write_archive(archive_path, files))

    assert find_unverified(archive_path, files) == []


def test_archive_keeps_same_named_files_apart(tmp_path):
    """Proves two camera files sharing a name are both archived, neither overwriting the other."""
    camera_dir = tmp_path / "DCIM"
    write_media(camera_dir, "100_PANA/P1000001.JPG", 64, 1)
    write_media(camera_dir, "101_PANA/P1000001.JPG", 32, 2)
    files = tuple(list_camera_files(camera_dir))

    archive_path = tmp_path / "archive.tar.gz"
    list(write_archive(archive_path, files))

    assert read_archive_sizes(archive_path) == {
        "100_PANA/P1000001.JPG": 64,
        "101_PANA/P1000001.JPG": 32,
    }
    assert find_unverified(archive_path, files) == []


def test_find_unverified_catches_a_missing_or_resized_file(tmp_path):
    """Proves verification fails when the archive lacks a file or holds a different size."""
    camera_dir = tmp_path / "DCIM"
    write_media(camera_dir, "A.JPG", 64, 1)
    files = tuple(list_camera_files(camera_dir))

    empty_archive = tmp_path / "empty.tar.gz"
    with tarfile.open(empty_archive, "w:gz"):
        pass

    assert find_unverified(empty_archive, files) == list(files)

    resized = (CameraFile(files[0].path, files[0].relative, 9999, files[0].modified),)
    archive_path = tmp_path / "archive.tar.gz"
    list(write_archive(archive_path, files))

    assert find_unverified(archive_path, resized) == list(resized)


def test_verify_refuses_to_continue_when_the_archive_is_wrong(tmp_path):
    """Proves a bad archive aborts the run, so no file is ever deleted unverified."""
    camera_dir = tmp_path / "DCIM"
    path = write_media(camera_dir, "A.JPG", 64, 1)
    files = tuple(list_camera_files(camera_dir))
    claimed = (CameraFile(files[0].path, files[0].relative, 9999, files[0].modified),)

    archive_path = tmp_path / "archive.tar.gz"
    list(write_archive(partial_path(archive_path), files))

    verify_input = {"files": [to_entry(media) for media in claimed], "archive_path": archive_path}
    with pytest.raises(RuntimeError):
        drive_job(free_verify_archive(FakeContext(FREE_SCOPE), verify_input))

    assert path.exists()
    assert not archive_path.exists()


def test_build_archive_path_never_overwrites(tmp_path):
    """Proves a second run over the same dates writes a new archive, not over the old one."""
    first = build_archive_path(tmp_path, date(2026, 5, 1), date(2026, 5, 3))
    first.write_bytes(b"")
    second = build_archive_path(tmp_path, date(2026, 5, 1), date(2026, 5, 3))

    assert first.name == "2026-05-01_2026-05-03.tar.gz"
    assert second.name == "2026-05-01_2026-05-03-2.tar.gz"


def test_build_run_plan_short_circuits_when_space_is_free(tmp_path, monkeypatch):
    """Proves a card already at the target is left completely untouched."""
    camera_dir = tmp_path / "DCIM"
    write_media(camera_dir, "A.JPG", 64, 1)
    monkeypatch.setattr(
        "mirror.workflows.free.command.require_removable_device", allow_test_camera
    )

    assert build_run_plan(str(camera_dir), 0.000001, no_preserve=True) is None


def test_delete_job_removes_media_and_counts_bytes(tmp_path):
    """Proves the delete job clears its file and reports the space it recovered."""
    camera_dir = tmp_path / "DCIM"
    write_media(camera_dir, "A.JPG", 64, 1)
    entry = to_entry(list_camera_files(camera_dir)[0])

    result = drive_job(free_delete_file(FakeContext(FREE_SCOPE), entry))

    assert result == {"freed": 64, "error": None}
    assert list_camera_files(camera_dir) == []


def test_delete_job_reports_a_failure_rather_than_raising(tmp_path):
    """Proves one unreadable file cannot fail the whole run."""
    camera_dir = tmp_path / "DCIM"
    write_media(camera_dir, "A.JPG", 64, 1)
    entry = to_entry(list_camera_files(camera_dir)[0])
    entry["path"] = str(camera_dir / "gone.JPG")

    result = drive_job(free_delete_file(FakeContext(FREE_SCOPE), entry))

    assert result["freed"] == 0
    assert "A.JPG" in result["error"]


def test_delete_job_keeps_the_camera_folders(tmp_path):
    """Proves emptied DCIM folders stay on the card, so the camera keeps writing to them."""
    camera_dir = tmp_path / "DCIM"
    write_media(camera_dir, "100_PANA/A.JPG", 64, 1)
    write_media(camera_dir, "101_PANA/B.JPG", 32, 2)

    for media in list_camera_files(camera_dir):
        drive_job(free_delete_file(FakeContext(FREE_SCOPE), to_entry(media)))

    assert (camera_dir / "100_PANA").is_dir()
    assert (camera_dir / "101_PANA").is_dir()


def test_summarise_deletes_totals_bytes_and_collects_failures():
    """Proves the run summary counts only the files that actually went."""
    results = [
        {"freed": 10, "error": None},
        {"freed": 0, "error": "B.JPG: busy"},
        {"freed": 5, "error": None},
    ]

    assert summarise_deletes(results) == {
        "deleted": 2,
        "freed": 15,
        "errors": ["B.JPG: busy"],
    }


def test_format_bytes_picks_a_readable_unit():
    """Proves byte counts print in the largest unit that keeps them above one."""
    cases = [(512, "512.0 B"), (2048, "2.0 KiB"), (5 * 1024**3, "5.0 GiB")]

    for count, expected in cases:
        assert format_bytes(count) == expected


def make_workflow_input(camera_dir: Path, archive_path: Path | None) -> dict:
    """Build the workflow input for every media file on a fake card."""
    files = [to_entry(media) for media in sorted(list_camera_files(camera_dir), key=str)]
    return {"files": files, "archive_path": str(archive_path) if archive_path else None}


def test_free_workflow_archives_and_verifies_before_deleting(tmp_path):
    """Proves the workflow never dispatches a delete before the archive is verified."""
    camera_dir = tmp_path / "DCIM"
    write_media(camera_dir, "100_PANA/A.JPG", 64, 1)
    write_media(camera_dir, "100_PANA/B.JPG", 32, 2)
    workflow_input = make_workflow_input(camera_dir, tmp_path / "archive.tar.gz")

    dispatched: list[str] = []
    summary = drive_job(
        free_workflow(FakeContext(FREE_SCOPE), workflow_input), dispatched=dispatched
    )

    assert dispatched.index("free_verify_archive") < dispatched.index("free_delete_file")
    assert dispatched.count("free_archive_file") == 2
    assert dispatched.count("free_delete_file") == 2
    assert summary == {"deleted": 2, "freed": 96, "errors": []}


def test_free_workflow_skips_the_archive_when_not_preserving(tmp_path):
    """Proves --no-preserve runs no archive or verify job, only deletes."""
    camera_dir = tmp_path / "DCIM"
    write_media(camera_dir, "A.JPG", 64, 1)
    workflow_input = make_workflow_input(camera_dir, None)

    dispatched: list[str] = []
    drive_job(free_workflow(FakeContext(FREE_SCOPE), workflow_input), dispatched=dispatched)

    assert dispatched == ["free_delete_file"]


def test_archive_job_signals_progress_once_per_file(tmp_path):
    """Proves each archived file fires its own semaphore, so progress tracks per file."""
    camera_dir = tmp_path / "DCIM"
    write_media(camera_dir, "100_PANA/A.JPG", 64, 1)
    write_media(camera_dir, "100_PANA/B.JPG", 32, 2)
    write_media(camera_dir, "101_PANA/C.JPG", 16, 3)
    archive_path = tmp_path / "archive.tar.gz"
    archive_input = make_workflow_input(camera_dir, archive_path)

    signalled: list[str] = []
    result = drive_job(
        free_archive_media(FakeContext(FREE_SCOPE), archive_input), signalled=signalled
    )

    assert result == {"archived": 3}
    assert signalled == ["free_archive_0", "free_archive_1", "free_archive_2"]


def test_verify_promotes_the_partial_archive(tmp_path):
    """Proves the archive only takes its final name once every file is verified."""
    camera_dir = tmp_path / "DCIM"
    write_media(camera_dir, "A.JPG", 64, 1)
    archive_path = tmp_path / "archive.tar.gz"
    archive_input = make_workflow_input(camera_dir, archive_path)

    drive_job(free_archive_media(FakeContext(FREE_SCOPE), archive_input))
    assert partial_path(archive_path).exists()
    assert not archive_path.exists()

    drive_job(free_verify_archive(FakeContext(FREE_SCOPE), archive_input))

    assert archive_path.exists()
    assert not partial_path(archive_path).exists()


def test_cancelling_mid_archive_deletes_nothing_and_leaves_no_final_archive(tmp_path):
    """Proves a cancelled run loses no media and leaves no archive that looks complete."""
    camera_dir = tmp_path / "DCIM"
    write_media(camera_dir, "100_PANA/A.JPG", 64, 1)
    write_media(camera_dir, "100_PANA/B.JPG", 32, 2)
    write_media(camera_dir, "101_PANA/C.JPG", 16, 3)
    archive_path = tmp_path / "archive.tar.gz"
    archive_input = make_workflow_input(camera_dir, archive_path)

    generator = free_archive_media(FakeContext(FREE_SCOPE), archive_input)
    generator.send(None)
    generator.close()

    assert len(list_camera_files(camera_dir)) == 3
    assert not archive_path.exists()
    assert partial_path(archive_path).name.endswith(PARTIAL_SUFFIX)


def test_resolve_camera_dir_refuses_a_card_it_cannot_write_to(tmp_path):
    """Proves an unwritable card fails before any archive work, not after it."""
    camera_dir = tmp_path / "DCIM"
    write_media(camera_dir, "A.JPG", 64, 1)
    camera_dir.chmod(0o555)

    try:
        with pytest.raises(PermissionError):
            resolve_camera_dir(str(camera_dir))
    finally:
        camera_dir.chmod(0o755)


def test_resolve_camera_dir_refuses_a_read_only_mount(tmp_path, monkeypatch):
    """Proves a card mounted read-only is rejected up front, whatever its permissions say."""
    camera_dir = tmp_path / "DCIM"
    write_media(camera_dir, "A.JPG", 64, 1)

    real_statvfs = os.statvfs

    def read_only_statvfs(path):
        stats = real_statvfs(path)
        return os.statvfs_result((
            stats.f_bsize,
            stats.f_frsize,
            stats.f_blocks,
            stats.f_bfree,
            stats.f_bavail,
            stats.f_files,
            stats.f_ffree,
            stats.f_favail,
            stats.f_flag | os.ST_RDONLY,
            stats.f_namemax,
        ))

    monkeypatch.setattr(os, "statvfs", read_only_statvfs)

    with pytest.raises(PermissionError):
        resolve_camera_dir(str(camera_dir))
