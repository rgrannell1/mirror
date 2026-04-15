"""Main Textual application: tabbed layout for photo and album labelling."""

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Footer, Header, TabbedContent, TabPane

from labeller.albums.pane import AlbumFilterProvider, AlbumPane
from labeller.photos.pane import PhotoFilterProvider, PhotoPane
from labeller.videos.pane import VideoFilterProvider, VideoPane
from labeller.widgets import load_places, load_subjects


class LabellerApp(App):
    """Tabbed labeller: Photos, Videos, and Albums tabs."""

    COMMANDS = App.COMMANDS | {PhotoFilterProvider, AlbumFilterProvider, VideoFilterProvider}

    CSS = """
    TabbedContent {
        height: 1fr;
    }

    TabPane {
        padding: 0;
    }

    PhotoPane, AlbumPane, VideoPane {
        height: 1fr;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit"),
    ]

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._places = load_places()
        self._subjects = load_subjects()
        self.last_edit: tuple[str, str] | None = None

    def compose(self) -> ComposeResult:
        yield Header()
        with TabbedContent():
            with TabPane("Photos", id="photos"):
                yield PhotoPane(places=self._places, subjects=self._subjects)
            with TabPane("Videos", id="videos"):
                yield VideoPane(places=self._places, subjects=self._subjects)
            with TabPane("Albums", id="albums"):
                yield AlbumPane(places=self._places)
        yield Footer()

    def on_mount(self) -> None:
        self.query_one(PhotoPane).query_one("FieldTable").focus()

    def on_tabbed_content_tab_activated(self, event: TabbedContent.TabActivated) -> None:
        if event.tab.id == "photos":
            self.query_one(PhotoPane).query_one("FieldTable").focus()
        elif event.tab.id == "albums":
            self.query_one(AlbumPane).query_one("FieldTable").focus()
        # Videos tab focus is handled by VideoPane.on_show
