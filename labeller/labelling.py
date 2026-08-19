"""Shared view plumbing for image labelling: worker dispatch and notifications."""

from functools import partial
from typing import NamedTuple

from rich.markup import escape
from textual.app import App
from textual.widget import Widget

from mirror.services.vision import label_image

# Most labels shown and copied from one identification.
MAX_LABELS_SHOWN = 6


class LabelRequest(NamedTuple):
    """Inputs for one image identification call."""

    fpath: str | None
    url: str
    album_title: str | None = None
    place_names: tuple[str, ...] = ()


def request_labels(pane: Widget, request: LabelRequest) -> None:
    """Notify, then identify the image on a worker thread."""
    pane.app.notify("Asking Gemini...", timeout=3)
    worker = partial(fetch_labels, pane.app, request)
    pane.run_worker(worker, exclusive=False, thread=True)


def fetch_labels(app: App, request: LabelRequest) -> None:
    """Call the vision service and surface the labels as a notification."""
    try:
        labels = label_image(
            request.fpath,
            request.url,
            album_title=request.album_title,
            place_names=list(request.place_names),
        )
    except Exception as exc:  # noqa: BLE001
        message = escape(f"Gemini API error: {exc}")
        app.call_from_thread(app.notify, message, severity="error", timeout=8)
        return
    if not labels:
        app.call_from_thread(app.notify, "No labels returned", severity="warning")
        return
    joined = "  •  ".join(labels[:MAX_LABELS_SHOWN])
    app.call_from_thread(app.copy_to_clipboard, joined)
    app.call_from_thread(app.notify, escape(joined), timeout=12)
