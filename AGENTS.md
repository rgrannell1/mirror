@/home/rg/Agents/AGENTS.md
@/home/rg/Agents/agents.python.md
@/home/rg/Agents/agents.zahir.md

- Please read /home/rg/Code/zahir for context about the workflow engine, especially the readme.
- Zahir writes workflow errors to `zahir_logs/latest.stderr` in the mirror project root.
- The media database is /home/rg/media.db. Use the `/mirror-db` skill for the full schema reference
- The media is in /home/rg/Media/<year>/<album>/Published/*
- Project outputs to linked project /home/rg/Code/websites/photos.rgrannell.xyz (../websites/photos.rgrannell.xyz)
- There is a TUI labeller for annotating photos
- `mirror` on PATH is a wrapper over `uv run --project`. A new dependency in `pyproject.toml` applies on the next call, with no reinstall
- Never install mirror with `uv tool install`. A tool install freezes its dependency set. It then fails with `ModuleNotFoundError` after each new dependency
- Run `rs install` only to rebuild the wrapper, for example after the repository moves
