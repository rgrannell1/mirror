import sys
from typing import Iterator
from src.ansi import ANSI
from src.database import SqliteDatabase
from src.media import IMedia
from src.phash import PHashReader, PhashData
from src.photo import Photo
from src.vault import MediaVault
from src.video import Video


commands = ["haystack scan", "hayscan link", "haystack copy"]

doc = f"""
{ANSI.bold("haystack")} 🌾
---------------------------------------------

Index external photos and videos
    {ANSI.green("haystack scan")}

---------------------------------------------
{ANSI.grey(" • ".join(commands))}"""

HAYSTACK_DATABASE_PATH = "/home/rg/haystack.db"


class MediaScanner:
    def __init__(self, dpaths: list[str], db: SqliteDatabase):
        self.dpaths = dpaths
        self.db = db

    def _unsaved_phashes(self) -> Iterator[PhashData]:
        """Return phashes for all photos not already stored in the database"""

        phash_table = self.db.phashes_table()

        for dpath in self.dpaths:
            for album in MediaVault(dpath).albums():
                for media in album.media():
                    if not Photo.is_a(media.fpath):
                        continue

                    if not phash_table.has(media.fpath):
                        yield PHashReader.phash(media.fpath)

    def scan(self) -> None:
        phash_table = self.db.phashes_table()
        photos_table = self.db.photos_table()
        videos_table = self.db.videos_table()

        current_fpaths = set()

        for entry in self._list_current_media():
            if isinstance(entry, Photo):
                photos_table.add(entry.fpath)
                current_fpaths.add(entry.fpath)
            elif isinstance(entry, Video):
                videos_table.add(entry.fpath)
                current_fpaths.add(entry.fpath)

        self.db.remove_deleted_files(current_fpaths)

        phash_table.add_many(self._unsaved_phashes())

    def _list_current_media(self) -> Iterator[IMedia]:
        """Return all media in the directory"""

        for dpath in self.dpaths:
            for album in MediaVault(dpath).albums():
                for media in album.media():
                    yield media


class Haystack:
    def scan(self, dpaths: list[str]) -> None:
        db = SqliteDatabase(HAYSTACK_DATABASE_PATH)

        return
        MediaScanner(dpaths, db).scan()


def main() -> None:
    args = sys.argv[1:]

    if not args:
        print(doc, file=sys.stderr)
        return

    haystack = Haystack()
    command = args[0]

    if command == "scan":
        haystack.scan(args[1:])
    else:
        print(f"Unknown command: {command}", file=sys.stderr)
        print(doc, file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
