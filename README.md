# Mirror

```sh
uv run mirror
```

Runs the Zahir workflow: enrich → scan vault + `albums.md` / `photos.md` → upload → publish (manifests + rewrite markdown).

**Add an album**

- Folder under `PHOTO_DIRECTORY` with `Published` media; one filename must contain `+cover`.
- `uv run mirror`, then fill `albums.md` / `photos.md` and run again.

**Annotate**

- Edit `albums.md` / `photos.md`, then `uv run mirror`.
