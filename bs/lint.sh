#!/bin/bash

ruff check "$@"
uv run vulture src/
