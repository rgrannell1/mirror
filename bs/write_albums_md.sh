#! /usr/bin/env sh

rs clean
rs build
uv run mirror write_metadata album > albums.md