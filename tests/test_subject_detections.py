"""Tests for subject bounding-box detection storage and workflow wiring."""

import sqlite3
from functools import partial
from types import SimpleNamespace

from mirror.cli import build_parser
from mirror.services.database import SqliteDatabase
from mirror.services.database.photos import SubjectDetectionsTable
from mirror.services.detector import build_prompt, prompt_for_type
from mirror.workflows.detect.utils import list_missing_detections
from mirror.workflows.workflow import publish_phase

PROMPT_CASES = [
    ("bird", "bird."),
    ("train", "train."),
    ("arthropod", "insect. spider. crab."),
    ("cnidaria", "jellyfish."),
    ("ctenophore", "jellyfish."),
    ("plane", "airplane."),
    ("spacecraft", "rocket. spacecraft."),
]


def test_prompt_for_type() -> None:
    """Proves every subject type maps to a lower-case prompt with a trailing full stop."""
    for subject_type, expected in PROMPT_CASES:
        assert prompt_for_type(subject_type) == expected


BUILD_PROMPT_CASES = [
    ("bird", (), "bird."),
    ("bird", ("Grey Heron",), "grey heron. bird."),
    ("bird", ("Grey Heron", "Robin"), "grey heron. robin. bird."),
    ("mammal", ("Mammal",), "mammal."),
    ("plane", ("Airplane",), "airplane."),
]


def test_build_prompt() -> None:
    """Proves subject names precede the type prompt, normalised and deduplicated."""
    for subject_type, names, expected in BUILD_PROMPT_CASES:
        assert build_prompt(subject_type, names) == expected


def make_scan(boxes: list, prompt: str, threshold: float = 0.35) -> dict:
    """Build a DetectionScan record for tests."""
    return {"boxes": boxes, "prompt": prompt, "threshold": threshold, "image_area": 1000}


def test_detections_round_trip() -> None:
    """Proves stored boxes read back intact, and an empty scan differs from no scan."""
    with SqliteDatabase(":memory:") as db:
        detections = db.subject_detections_table()
        boxes = [{"coords": [1.0, 2.0, 30.5, 40.0], "volume": 1121, "confidence": 0.8}]

        detections.add("h1", "bird", make_scan(boxes, "bird."))
        detections.add("h2", "train", make_scan([], "train."))

        assert detections.get("h1", "bird") == boxes
        assert detections.get("h2", "train") == []
        assert detections.get("h3", "bird") is None
        assert detections.has("h1", "bird")
        assert not detections.has("h1", "train")
        assert detections.list_scan_provenance() == {
            ("h1", "bird"): ("bird.", 0.35),
            ("h2", "train"): ("train.", 0.35),
        }


def test_detections_add_replaces() -> None:
    """Proves re-detection overwrites the stored boxes and provenance for a pair."""
    with SqliteDatabase(":memory:") as db:
        detections = db.subject_detections_table()
        detections.add("h1", "bird", make_scan([], "bird.", 0.45))
        replacement = [{"coords": [0.0, 0.0, 5.0, 5.0], "volume": 25, "confidence": 0.5}]

        detections.add("h1", "bird", make_scan(replacement, "robin. bird."))

        assert detections.get("h1", "bird") == replacement
        assert detections.list_scan_provenance() == {("h1", "bird"): ("robin. bird.", 0.35)}


def test_box_volume_migration() -> None:
    """Proves boxes stored before the volume field gain it, computed from coords."""
    conn = sqlite3.connect(":memory:")
    SubjectDetectionsTable(conn)
    conn.execute(
        "insert into subject_detections (phash, subject_type, boxes, prompt) values"
        " ('h1', 'bird', '[{\"coords\": [10.0, 20.0, 110.0, 70.0], \"confidence\": 0.5}]', 'bird.')"
    )
    conn.commit()

    detections = SubjectDetectionsTable(conn)

    assert detections.get("h1", "bird") == [
        {"coords": [10.0, 20.0, 110.0, 70.0], "confidence": 0.5, "volume": 5000}
    ]


def test_provenance_column_migration() -> None:
    """Proves pre-provenance tables gain the columns and keep their rows as 0.45 scans."""
    conn = sqlite3.connect(":memory:")
    conn.execute(
        "create table subject_detections ("
        " phash text not null, subject_type text not null, boxes text not null,"
        " primary key (phash, subject_type))"
    )
    conn.execute("insert into subject_detections values ('h1', 'bird', '[]')")

    detections = SubjectDetectionsTable(conn)

    assert detections.list_scan_provenance() == {("h1", "bird"): ("", 0.45)}


def add_subject(db: SqliteDatabase, phash: str, target: str) -> None:
    """Insert one subject metadata row."""
    db.conn.execute(
        "insert into photo_metadata_table (phash, src_type, relation, target)"
        " values (?, 'photo', 'subject', ?)",
        (phash, target),
    )


def seed_photo_files(db: SqliteDatabase, tmp_path) -> str:
    """Register a real and a missing photo file in phashes; return the real path."""
    real_fpath = str(tmp_path / "real.jpg")
    with open(real_fpath, "w") as file_handle:
        file_handle.write("stub")

    db.conn.execute("insert into phashes values (?, ?)", (real_fpath, "h1"))
    db.conn.execute("insert into phashes values (?, ?)", (str(tmp_path / "gone.jpg"), "h2"))
    return real_fpath


def make_detection_db(tmp_path) -> tuple[SqliteDatabase, str]:
    """Build a database with one detectable pair among skippable ones."""
    db = SqliteDatabase(":memory:")
    db.photo_metadata_table()
    db.phashes_table()
    db.subject_detections_table()
    real_fpath = seed_photo_files(db, tmp_path)

    # two bird species on one photo: one detection pair
    add_subject(db, "h1", "urn:ró:bird:robin")
    add_subject(db, "h1", "urn:ró:bird:wren")
    # file missing from disk: skipped
    add_subject(db, "h2", "urn:ró:train:dart")
    # already scanned with current prompt and threshold: skipped
    add_subject(db, "h1", "urn:ró:mammal:fox")
    db.conn.commit()
    db.subject_detections_table().add("h1", "mammal", make_scan([], "mammal."))

    return db, real_fpath


OWL_URN = "urn:ró:bird:tyto-alba"
OWL_NAMES = {OWL_URN: "Barn Owl"}


def test_list_missing_detections(tmp_path) -> None:
    """Proves only unscanned pairs with a file on disk are queued, once each."""
    db, real_fpath = make_detection_db(tmp_path)

    assert list(list_missing_detections(db, {})) == [("h1", "bird", real_fpath, ())]
    db.close()


def test_list_missing_detections_carries_names(tmp_path) -> None:
    """Proves pairs carry the names of their subjects, sorted, query strings stripped."""
    db, real_fpath = make_detection_db(tmp_path)
    add_subject(db, "h1", f"{OWL_URN}?seen=1")
    db.conn.commit()

    pairs = list(list_missing_detections(db, OWL_NAMES))
    assert pairs == [("h1", "bird", real_fpath, ("Barn Owl",))]
    db.close()


def test_stale_prompt_rows_re_scan(tmp_path) -> None:
    """Proves a stored row is re-queued when names change the prompt it was scanned with."""
    db, real_fpath = make_detection_db(tmp_path)
    add_subject(db, "h1", OWL_URN)
    db.conn.commit()
    db.subject_detections_table().add("h1", "bird", make_scan([], "bird."))

    pairs = list(list_missing_detections(db, OWL_NAMES))
    assert pairs == [("h1", "bird", real_fpath, ("Barn Owl",))]

    # re-scan with the name prompt at the current threshold marks it fresh
    db.subject_detections_table().add("h1", "bird", make_scan([], "barn owl. bird."))
    assert list(list_missing_detections(db, OWL_NAMES)) == []
    db.close()


def test_legacy_prompt_rows_always_re_scan(tmp_path) -> None:
    """Proves rows without a recorded prompt are always stale: their prompt is unknown."""
    db, real_fpath = make_detection_db(tmp_path)
    db.subject_detections_table().add("h1", "bird", make_scan([], ""))

    pairs = list(list_missing_detections(db, {}))
    assert pairs == [("h1", "bird", real_fpath, ())]
    db.close()


def test_stale_threshold_rows_re_scan(tmp_path) -> None:
    """Proves a stored row is re-queued when the confidence threshold changes."""
    db, real_fpath = make_detection_db(tmp_path)
    # scanned with the current prompt but the old 0.45 threshold
    db.subject_detections_table().add("h1", "bird", make_scan([], "bird.", 0.45))

    pairs = list(list_missing_detections(db, {}))
    assert pairs == [("h1", "bird", real_fpath, ())]
    db.close()


def test_no_github_flag_parses() -> None:
    """Proves --no-github reaches the workflow input as no_github."""
    assert build_parser().parse_args(["--no-github"]).no_github
    assert not build_parser().parse_args([]).no_github


def record_dispatch(calls: list, results: dict, name: str, input: dict) -> dict:
    """Record a scope dispatch and tag it so the driver can answer it."""
    calls.append(name)
    return {"fake_job": name}


class FakeScope:
    """Stands in for ctx.scope; every job dispatch is recorded."""

    def __init__(self, calls: list, results: dict) -> None:
        self.calls = calls
        self.results = results

    def __getattr__(self, name: str):
        return partial(record_dispatch, self.calls, self.results, name)


def drive_job(generator, results: dict) -> str:
    """Run a job generator, answering each fake dispatch with a canned result."""
    try:
        effect = generator.send(None)
        while True:
            if isinstance(effect, dict) and "fake_job" in effect:
                effect = generator.send(results.get(effect["fake_job"], {}))
            else:
                effect = generator.send(None)
    except StopIteration as stop:
        return stop.value


def run_publish_phase(tmp_path, workflow_input: dict) -> tuple[str, list]:
    """Drive publish_phase against a fake scope; return its summary and dispatches."""
    results = {
        "publish_artifacts": {"publication_id": "pid"},
        "publish_github": "pushed things",
    }
    (tmp_path / "tribbles-expanded.pid.txt").write_text("stub")
    paths = {"output_dir": str(tmp_path)}

    calls: list = []
    ctx = SimpleNamespace(scope=FakeScope(calls, results))
    summary = drive_job(publish_phase(ctx, workflow_input, paths), results)
    return summary, calls


def test_no_github_skips_publish(tmp_path) -> None:
    """Proves --no-github stops the pipeline before the GitHub publish step."""
    summary, calls = run_publish_phase(tmp_path, {"no_github": True})

    assert summary == "github publish skipped (--no-github)"
    assert "publish_github" not in calls


def test_github_publishes_by_default(tmp_path) -> None:
    """Proves the pipeline still publishes to GitHub without the flag."""
    summary, calls = run_publish_phase(tmp_path, {})

    assert summary == "published to github: pushed things"
    assert "publish_github" in calls
