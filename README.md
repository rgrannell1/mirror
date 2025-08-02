# Mirror

```sh
mirror scan
mirror upload
mirror publish
mirror read_metadata
mirror write_metadata
```

# Workflows

**Add an Album**

- Create folder in Media
- Published directory
- Add photos or videos
- Add +cover to one filepath
- `rs upload`
- `rs clean; rs build; uv run mirror write_metadata album > albums.md`
- Fill in details

**Annotate Photos**

- `rs clean; rs build; uv run mirror write_metadata photo > photos.md`
- Add geonames, species, etc
- `rs clean; rs build; uv run mirror read_metadata photo < photos.md`
- `rs scan`
- `rs publish`