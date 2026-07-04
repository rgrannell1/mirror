#!/bin/bash
# Report reasons publication will fail; exits non-zero if any blocking issue exists.
uv run mirror audit "$@"
