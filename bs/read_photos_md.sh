#! /usr/bin/env sh

rs clean
rs build
uv run mirror read_metadata photo < photos.md
