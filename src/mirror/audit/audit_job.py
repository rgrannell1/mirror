"""Pipeline gate: a zahir job that aborts publication when blocking audit findings exist."""

from collections.abc import Generator
from typing import Any

from zahir import JobContext

from mirror.audit.report import run_audit, summarise_findings
from mirror.commons.config import DATABASE_PATH
from mirror.commons.exceptions import MirrorAuditError
from mirror.services.database import SqliteDatabase


def audit_media(ctx: JobContext, input: dict) -> Generator[Any, Any, dict]:
    """Run blocking checks after upload and before publish; abort the pipeline if any fire."""
    with SqliteDatabase(DATABASE_PATH) as db:
        findings = run_audit(db)

    if findings:
        summary = summarise_findings(findings)
        message = f"publication blocked: {summary}; run `mirror audit` for details"
        raise MirrorAuditError(message)

    return {"findings": 0}  # noqa: B901 — zahir jobs return values from generators
    yield
