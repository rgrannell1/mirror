#!/usr/bin/env python3

import sys
from src.ansi import ANSI
from src.commands.publisher import ArtifactBuilder
from src.cdn import CDN
from src.config import DATABASE_PATH, OUTPUT_DIRECTORY, PHOTO_DIRECTORY
from src.database import SqliteDatabase
from src.commands.uploader import MediaUploader
from src.commands.scanner import MediaScanner, LinnaeusScanner
from src.metadata import JSONAlbumMetadataReader, JSONAlbumMetadataWriter, MarkdownTablePhotoMetadataReader, MarkdownTablePhotoMetadataWriter

commands = ["mirror scan", "mirror upload", "mirror publish", "mirror read_metadata", "mirror write_metadata"]

doc = f"""
{ANSI.bold("mirror")} 🪞
---------------------------------------------

Index photos and videos
    {ANSI.green("mirror scan")}
Encode and upload photos and videos to a CDN
    {ANSI.green("mirror upload")}
Publish the album artifacts
    {ANSI.green("mirror publish")}
Read album or photo metadata from stdin
    {ANSI.green("mirror read_metadata")}
Write album or photo metadata to stdout
    {ANSI.green("mirror write_metadata")}

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

    def read_metadata(self, content: str) -> None:
        """Read album or photo semantic information from stdin"""

        db = SqliteDatabase(DATABASE_PATH)

        if content not in ['photo', 'album']:
            print(f"Unknown content type: {content}", file=sys.stderr)
            return

        if content == 'photo':
            md_reader = MarkdownTablePhotoMetadataReader("/dev/stdin")

            db.write_photo_metadata(md_reader.read_photo_metadata(db))
        else:
            json_reader = JSONAlbumMetadataReader("/dev/stdin")

            db.write_album_metadata(json_reader.list_album_metadata(db))

    def write_metadata(self, content: str) -> None:
        """Output album or photo semantic information to stdout"""

        db = SqliteDatabase(DATABASE_PATH)

        if content not in ['photo', 'album']:
            print(f"Unknown content type: {content}", file=sys.stderr)
            return

        if content == 'photo':
            photo_writer = MarkdownTablePhotoMetadataWriter()
            photo_writer.write_photo_metadata(db)
        else:
            album_writer = JSONAlbumMetadataWriter()
            album_writer.write_album_metadata(db)


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
        mirror.write_metadata(args[1])
    elif command == "read_metadata":
        mirror.read_metadata(args[1])
    else:
        print(f"Unknown command: {command}", file=sys.stderr)
        print(doc, file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
