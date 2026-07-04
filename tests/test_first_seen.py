"""Regression tests for first-seen timestamp derivation (photos + videos)."""

import os

import ffmpeg

from mirror.data.semantic_triples import first_seen


def test_exif_created_at_to_unix_ms():
    """EXIF DATE_FORMAT strings convert to millisecond Unix time (UTC)."""
    assert first_seen._exif_created_at_to_unix_ms("1970:01:01 00:00:01") == 1000


def test_probe_reads_creation_time(monkeypatch):
    """A video's container creation_time is used as its capture time."""
    monkeypatch.setattr(
        ffmpeg,
        "probe",
        lambda fpath: {"format": {"tags": {"creation_time": "1970-01-01T00:00:01+00:00"}}},
    )
    assert first_seen._probe_creation_time_ms("/x.mp4") == 1000


def test_probe_handles_zulu_suffix(monkeypatch):
    """The `Z` UTC suffix (as ffprobe emits) parses correctly."""
    monkeypatch.setattr(
        ffmpeg,
        "probe",
        lambda fpath: {"format": {"tags": {"creation_time": "1970-01-01T00:00:02.000000Z"}}},
    )
    assert first_seen._probe_creation_time_ms("/x.mp4") == 2000


def test_video_capture_prefers_creation_time_over_mtime(monkeypatch, tmp_path):
    """creation_time wins over mtime — bulk re-imports leave mtime years wrong,
    so a filmed species must not be dated by its copy date."""
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"x")
    os.utime(video, (9_999_999, 9_999_999))  # mtime far in the future vs the tag
    monkeypatch.setattr(
        ffmpeg,
        "probe",
        lambda fpath: {"format": {"tags": {"creation_time": "1970-01-01T00:00:01+00:00"}}},
    )
    assert first_seen._video_capture_unix_ms(str(video)) == 1000


def test_video_capture_falls_back_to_mtime(monkeypatch, tmp_path):
    """With no creation_time tag, fall back to the file mtime."""
    monkeypatch.setattr(ffmpeg, "probe", lambda fpath: {"format": {"tags": {}}})
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"x")
    os.utime(video, (1000, 1000))
    assert first_seen._video_capture_unix_ms(str(video)) == 1000 * 1000


def test_video_capture_missing_file_returns_none(monkeypatch):
    """A subject whose video is absent and untagged yields no timestamp."""
    monkeypatch.setattr(ffmpeg, "probe", lambda fpath: {"format": {"tags": {}}})
    assert first_seen._video_capture_unix_ms("/does/not/exist.mp4") is None


def test_merge_earliest_keeps_minimum_and_collapses_qs():
    """Query-string variants collapse to one URN, keeping the earliest sighting."""
    earliest: dict[str, int] = {}
    first_seen._merge_earliest(earliest, "urn:ró:bird:x?context=wild", 500)
    first_seen._merge_earliest(earliest, "urn:ró:bird:x?context=captivity", 200)
    first_seen._merge_earliest(earliest, "urn:ró:bird:x", 900)
    assert earliest == {"urn:ró:bird:x": 200}
