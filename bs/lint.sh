#!/bin/bash

set -euo pipefail

ruff check "$@"
uv run --extra dev pyright src/mirror labeller
# Zahir jobs require unreachable trailing yields, which Vulture treats as dead code.
uv run vulture src/ --min-confidence 80 \
  --exclude "src/mirror/audit/audit_job.py,src/mirror/workflows"
