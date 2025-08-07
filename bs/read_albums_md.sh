#! /usr/bin/env sh

rs clean
rs build
uv run mirror read_metadata album < albums.md
