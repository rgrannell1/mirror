#!/bin/bash
# Install mirror as a global uv tool, exposing the `mirror` command on PATH.
set -euo pipefail
uv tool install --force --editable .
