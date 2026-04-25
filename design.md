# Mirror — Design

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

## How Triples Are Generated

Album and photo identity flows from `albums.md` → `media_metadata_table` → views → triple readers → `triples.<id>.json`.

- `media_metadata_table` is the source of truth for album metadata. Each row is `(src=dpath, src_type='album', relation, target)`. The `permalink` relation holds the album ID slug (e.g. `puerto-de-la-cruz-25`). `ReadAlbums` **wipes all album rows and rewrites from scratch** on every run.
- `view_album_data` joins all distinct dpaths found in the `photos` / `videos` tables against `media_metadata_table`. The album's `id` column is the `permalink` target for that dpath.
- `view_photo_data` joins `photos` (keyed by `fpath`/`dpath`) with `view_album_data` to derive `album_id`, and with `encoded_photos` to get CDN URLs.
- `AlbumTriples` (in `data/semantic_triples/albums.py`) reads `view_album_data` and emits one block of triples per album under `urn:ró:album:<id>`.
- `PhotoTriples` (in `data/semantic_triples/photos.py`) reads `view_photo_data` and emits one block per photo, including `album_id`.

**Renaming an album ID** (permalink only, folder unchanged): edit the `permalink` column in `albums.md`, then re-run the pipeline. `ReadAlbums` clears and re-inserts all album metadata, so the old ID is fully gone before `PublishTriples` runs. Publishing without first running `ReadAlbums` will emit triples for the stale old ID.

**Null-id risk**: if `view_album_data` returns a row with `id = NULL` (dpath present in `photos` but no matching permalink in `media_metadata_table`), `AlbumTriples` will emit `urn:ró:album:None` and `PhotoTriples` will emit photos with `album_id = None` — both cause frontend parse failures. Guard: always run `ReadAlbums` before `PublishTriples`, or add `if album.id is None: continue` in `AlbumTriples.read()`.

## Cover Triples

Three readers emit `photo → cover → target` triples used by the frontend to display representative images:

- **`ListingCoverReader`** — one cover per top-level listing type (bird, mammal, reptile, amphibian, fish, insect, plane, train, car, place). For places, prefers landscape genre photos then falls back to highest-rated. All other types use highest-rated only. Target URN: `urn:ró:listing:<type>`.

- **`ThingCoverReader`** — one cover per individual thing (a specific bird, place, etc.). Explicit `cover` relations in `photo_metadata_table` take priority; otherwise highest-rated photo referencing that thing via `subject` or `location` is used. Target URN: `urn:ró:<type>:<id>`.

- **`PlaceFeatureCoverReader`** — one cover per place feature (castle, beach, volcano, etc.). Loads the feature→places mapping from `things.toml`, queries the DB for all photos whose `location` is one of those places, then picks the best per feature (landscape preferred, then highest-rated). Target URN: `urn:ró:place_feature:<id>`.

## Adding a New Album

1. Add folder under `PHOTO_DIRECTORY` with `Published/` media; one filename must contain `+cover`
2. Run `uv run mirror` to scan and upload
3. Fill in `albums.md` and `photos.md` with metadata
4. Run `uv run mirror` again to publish
