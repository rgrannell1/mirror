"""Protect the boundary between service adapters and Zahir workflow code."""

import ast
from pathlib import Path

# Service modules under review.
SERVICE_PATH = Path("src/mirror/services")

# Workflow modules that can contain Zahir jobs.
WORKFLOW_PATH = Path("src/mirror/workflows")

# Engines that must remain outside service modules.
WORKFLOW_ENGINES = {"bookman", "orbis", "tertius", "zahir"}

# External adapters that Zahir jobs must access through services.
ADAPTER_MODULES = {"psutil", "requests", "shutil", "sqlite3", "subprocess", "tarfile"}


def imported_modules(path: Path) -> set[str]:
    """Return every module imported by one Python file."""
    tree = ast.parse(path.read_text(), filename=str(path))
    modules = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


def test_services_do_not_depend_on_workflows():
    """Proves services remain independent from workflows and workflow engines."""
    violations = []
    for path in SERVICE_PATH.rglob("*.py"):
        imports = imported_modules(path)
        forbidden = {
            module
            for module in imports
            if module.startswith("mirror.workflows") or module.split(".")[0] in WORKFLOW_ENGINES
        }
        if forbidden:
            violations.append((str(path), sorted(forbidden)))
    assert not violations


def test_zahir_jobs_do_not_import_service_adapters():
    """Proves Zahir job modules use service modules for external adapters."""
    violations = []
    for path in WORKFLOW_PATH.rglob("*.py"):
        source = path.read_text()
        if "JobContext" not in source:
            continue
        forbidden = imported_modules(path) & ADAPTER_MODULES
        if forbidden:
            violations.append((str(path), sorted(forbidden)))
    assert not violations
