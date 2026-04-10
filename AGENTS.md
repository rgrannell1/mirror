
- Please read /home/rg/Code/zahir for context about the workflow engine, especially the readme.
- No single letter variables. Err for exceptions, idx for indices.
- Use `sqlite` CLI command, not `sqlite3`
- The media database is /home/rg/media.db
- The media is in /home/rg/Media/<year>/<album>/Published/*
- Project outputs to linked project /home/rg/Code/websites/photos.rgrannell.xyz
- Use uv

# Project Overview

Mirror is a media asset management and publishing pipeline for a photography website. It manages photos and videos stored in `~/Drive/Media/<year>/<album>/Published/`, uploads them to a CDN, and publishes JSON artifacts consumed by the frontend at `~/Code/websites/photos.rgrannell.xyz`.

## Commands

```sh
uv run mirror          # Run the full pipeline
uv run ruff check src  # Lint
uv run ruff format src # Format
```

No test suite exists in this repo.

## Workflow Architecture

The pipeline is orchestrated by the `zahir` workflow engine (local dependency at `~/Code/zahir`). Each stage is a `@spec()`-decorated generator function that yields `JobInstance`, `Await`, `JobOutputEvent`, or `WorkflowOutputEvent`. `Await` suspends until a dependency resolves; multiple specs can run concurrently via `LocalWorkflow(context, max_workers=15)`.

**Pipeline order** (`MirrorWorkflow` in `src/mirror/workflows/workflow.py`):

1. **Enrich** (`workflows/enrich/`) — reads `things.toml`, enriches place data
2. **Scan** (`workflows/scan/`) — indexes media files into SQLite, reads `albums.md` + `photos.md` metadata, fetches Geonames + Wikidata
3. **Upload** (`workflows/upload/`) — encodes photos/videos, uploads to CDN (DigitalOcean Spaces), stores URLs in SQLite
4. **Publish** (`workflows/publish/`) — reads SQLite, writes `env.json`, `stats.<id>.json`, `triples.<id>.json` into the output directory; also rewrites `albums.md` and `photos.md`

## Key Files and Data Flow

- `src/mirror/cli.py` — entry point; registers all specs and starts `MirrorWorkflow`
- `src/mirror/services/database/facade.py` — `SqliteDatabase` facade over `~/media.db`; provides typed table/view accessors
- `src/mirror/services/cdn.py` — uploads encoded media to S3-compatible CDN
- `src/mirror/services/encoder.py` — PIL/OpenCV photo encoding; computes perceptual hashes, contrasting grey, mosaic colours
- `src/mirror/services/metadata.py` — reads/writes `albums.md` and `photos.md` markdown tables
- `src/mirror/commons/config.py` — all paths/env vars (DATABASE_PATH, PHOTO_DIRECTORY, OUTPUT_DIRECTORY, SPACES_* credentials)
- `albums.md` / `photos.md` — human-edited markdown tables at repo root; source of album titles, summaries, countries, photo captions

## Environment Variables

Required in `.env` or environment:
- `SPACES_REGION`, `SPACES_ENDPOINT_URL`, `SPACES_BUCKET`, `SPACES_ACCESS_KEY_ID`, `SPACES_SECRET_KEY` — CDN credentials
- `GEONAMES_USERNAME` — for Geonames API lookups
- `PHOTO_DIRECTORY`, `DATABASE_PATH`, `OUTPUT_DIRECTORY` — override default paths

## Adding a New Album

1. Add folder under `PHOTO_DIRECTORY` with `Published/` media; one filename must contain `+cover`
2. Run `uv run mirror` to scan and upload
3. Fill in `albums.md` and `photos.md` with metadata
4. Run `uv run mirror` again to publish
