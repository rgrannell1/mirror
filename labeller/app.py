"""Main Textual application: tabbed layout for photo and album labelling."""

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Footer, Header, TabbedContent, TabPane

from labeller.albums.pane import AlbumFilterProvider, AlbumPane
from labeller.photos.pane import PhotoFilterProvider, PhotoPane


class LabellerApp(App):
    """Tabbed labeller: Photos and Albums tabs."""

    COMMANDS = App.COMMANDS | {PhotoFilterProvider, AlbumFilterProvider}

    CSS = """
    TabbedContent {
        height: 1fr;
    }

    TabPane {
        padding: 0;
    }

    PhotoPane, AlbumPane {
        height: 1fr;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit"),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        with TabbedContent():
            with TabPane("Photos", id="photos"):
                yield PhotoPane()
            with TabPane("Albums", id="albums"):
                yield AlbumPane()
        yield Footer()

    def on_mount(self) -> None:
        self.query_one(PhotoPane).query_one("FieldTable").focus()

    def on_tabbed_content_tab_activated(self, event: TabbedContent.TabActivated) -> None:
        if event.tab.id == "photos":
            self.query_one(PhotoPane).query_one("FieldTable").focus()
        elif event.tab.id == "albums":
            self.query_one(AlbumPane).query_one("FieldTable").focus()
