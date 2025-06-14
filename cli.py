import sys
from src.ansi import ANSI
from src.commands.publisher import ArtifactBuilder
from src.cdn import CDN
from src.config import DATABASE_PATH, OUTPUT_DIRECTORY, PHOTO_DIRECTORY
from src.database import SqliteDatabase
from src.commands.uploader import MediaUploader
from src.commands.scanner import MediaScanner, LinnaeusScanner
from src.metadata import JSONAlbumMetadataReader, JSONAlbumMetadataWriter

commands = ["mirror scan", "mirror upload", "mirror publish"]

doc = f"""
{ANSI.bold("mirror")} 🪞
---------------------------------------------

Index photos and videos & metadata sources
    {ANSI.green("mirror scan")}
Encode and upload photos and videos to a CDN
    {ANSI.green("mirror upload")}
Publish the generated artifacts
    {ANSI.green("mirror publish")}

---------------------------------------------
{ANSI.grey(" • ".join(commands))}"""


class Mirror:
    def scan(self, dpath: str) -> None:
        db = SqliteDatabase(DATABASE_PATH)

        MediaScanner(dpath, db).scan()
        LinnaeusScanner(db).scan()

    def upload(self) -> None:
        db = SqliteDatabase(DATABASE_PATH)
        uploader = MediaUploader(db, CDN())

        uploader.upload()

    def publish(self) -> None:
        db = SqliteDatabase(DATABASE_PATH)

        builder = ArtifactBuilder(db, OUTPUT_DIRECTORY)
        builder.build()

    def read_metadata(self) -> None:
        """Read album or photo semantic information from stdin"""
        # TODO validate against the schema
        ...

        db = SqliteDatabase(DATABASE_PATH)
        reader = JSONAlbumMetadataReader('/dev/stdin')

        for item in reader.list_album_metadata(db):
            # update the existing table, wiping all previous information
            print(item)

    def write_metadata(self) -> None:
        """Output album or photo semantic information to stdout"""

        db = SqliteDatabase(DATABASE_PATH)
        writer = JSONAlbumMetadataWriter()

        writer.write_album_metadata(db)


def main() -> None:
    args = sys.argv[1:]

    if not args:
        print(doc, file=sys.stderr)
        return

    mirror = Mirror()
    command = args[0]

    if command == "scan":
        mirror.scan(PHOTO_DIRECTORY)
    elif command == "upload":
        mirror.upload()
    elif command == "publish":
        mirror.publish()
    elif command == "write_metadata":
        mirror.write_metadata()
    elif command == "read_metadata":
        mirror.read_metadata()
    else:
        print(f"Unknown command: {command}", file=sys.stderr)
        print(doc, file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
