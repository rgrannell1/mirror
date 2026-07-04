"""Run the audit checks and render their findings as a grouped, colourised report."""

from collections import defaultdict

from mirror.audit.audit_types import Finding
from mirror.audit.checks import CHECKS
from mirror.commons.ansi import ANSI
from mirror.commons.config import PHOTO_DIRECTORY
from mirror.services.database import SqliteDatabase


def run_audit(db: SqliteDatabase) -> list[Finding]:
    """Run every registered check and collect all blocking findings."""
    findings: list[Finding] = []
    for check in CHECKS:
        findings.extend(check.run(db))
    return findings


def shorten_subject(subject: str) -> str:
    """Trim the media-root prefix so album and photo paths read compactly."""
    prefix = f"{PHOTO_DIRECTORY}/"
    if subject.startswith(prefix):
        return subject[len(prefix) :]
    return subject


def summarise_findings(findings: list[Finding]) -> str:
    """One-line count of findings and how many checks they span."""
    checks_hit = len({finding.check for finding in findings})
    return f"{len(findings)} blocking issue(s) across {checks_hit} check(s)"


def group_by_check(findings: list[Finding]) -> dict[str, list[Finding]]:
    """Bucket findings under their check slug."""
    grouped: dict[str, list[Finding]] = defaultdict(list)
    for finding in findings:
        grouped[finding.check].append(finding)
    return grouped


def format_findings(findings: list[Finding]) -> str:
    """Render findings grouped by check, or a success line when there are none."""
    if not findings:
        return ANSI.green("✓ No publication-blocking issues found.")

    grouped = group_by_check(findings)
    lines: list[str] = []

    for check in CHECKS:
        group = grouped.get(check.slug)
        if not group:
            continue
        lines.append(ANSI.bold(ANSI.red(f"✗ {check.description} ({len(group)})")))
        for finding in group:
            subject = shorten_subject(finding.subject)
            lines.append(ANSI.grey(f"  • {subject} — {finding.detail}"))
        lines.append("")

    lines.append(ANSI.bold(summarise_findings(findings)))
    return "\n".join(lines)
