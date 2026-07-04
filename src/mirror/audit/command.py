"""CLI entry for `mirror audit`: run the checks, print the report, return an exit code."""

from mirror.audit.report import format_findings, run_audit
from mirror.commons.config import DATABASE_PATH
from mirror.services.database import SqliteDatabase


def run_audit_command() -> int:
    """Run the audit, print the grouped report, and return a shell exit code."""
    with SqliteDatabase(DATABASE_PATH) as db:
        findings = run_audit(db)
    print(format_findings(findings))
    return 1 if findings else 0
