"""Tests for workflow runner package imports."""

import importlib
import sys

import pytest


def is_runner_dependency(module_name: str) -> bool:
    """Return whether a loaded module can affect runner import order."""

    return module_name == "mirror.workflows.runner" or module_name.startswith(
        "mirror.workflows.free"
    )


def test_runner_imports_before_free_command(monkeypatch: pytest.MonkeyPatch):
    """Proves runner import does not depend on prior free-package initialisation."""

    for module_name in tuple(sys.modules):
        if is_runner_dependency(module_name):
            monkeypatch.delitem(sys.modules, module_name)

    runner = importlib.import_module("mirror.workflows.runner")

    assert callable(runner.run_workflow)
