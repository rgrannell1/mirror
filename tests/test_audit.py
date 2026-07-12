"""Tests for publication audit rules."""

import sqlite3
from types import SimpleNamespace

from mirror.audit import checks


def make_metadata_db(targets: list[tuple[str, str]]) -> SimpleNamespace:
    """Build the metadata tables used by the animal-name audit."""
    conn = sqlite3.connect(":memory:")
    conn.execute("create table photo_metadata_table (relation text, target text)")
    conn.execute("create table video_metadata_table (relation text, target text)")
    for table, target in targets:
        conn.execute(f"insert into {table} values ('subject', ?)", (target,))
    return SimpleNamespace(conn=conn)


def test_animals_missing_names_reports_distinct_canonical_urns(tmp_path, monkeypatch) -> None:
    """Proves referenced animals need one non-empty name definition."""
    things_path = tmp_path / "things.toml"
    things_path.write_text(
        """
[[birds]]
id = "urn:ró:bird:named"
name = "Named bird"

[[mammals]]
id = "urn:ró:mammal:blank"
name = ""
""",
        encoding="utf-8",
    )
    monkeypatch.setattr(checks, "DEFAULT_THINGS_PATH", things_path)
    db = make_metadata_db([
        ("photo_metadata_table", "urn:ró:bird:named"),
        ("photo_metadata_table", "urn:ró:mammal:blank?context=wild"),
        ("video_metadata_table", "urn:ró:mammal:blank"),
        ("video_metadata_table", "urn:ró:reptile:missing"),
        ("video_metadata_table", "urn:ró:plane:not-an-animal"),
    ])

    findings = list(checks.check_animals_missing_names(db))

    assert [finding.subject for finding in findings] == [
        "urn:ró:mammal:blank",
        "urn:ró:reptile:missing",
    ]
