#!/bin/bash

ruff check "$@"
uv run --extra dev pyright src/mirror labeller
uv run vulture src/
