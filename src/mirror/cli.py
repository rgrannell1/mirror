#!/usr/bin/env python3

import sys
from mirror.ansi import ANSI
from mirror.commands import write_metadata
from mirror.commands.write_triples import write_neo4j_triples
from mirror.commands.publisher import ArtifactBuilder
from mirror.cdn import CDN, D1Builder
from mirror.commands.read_metadata import read_metadata
from mirror.commands.write_metadata import write_metadata
from mirror.config import DATABASE_PATH, OUTPUT_DIRECTORY, PHOTO_DIRECTORY
from mirror.database import SqliteDatabase
from mirror.commands.uploader import MediaUploader
from mirror.commands.scanner import GeonamesScanner, MediaScanner, WikidataScanner

commands = ["mirror scan", "mirror upload", "mirror publish", "mirror read_metadata", "mirror write_metadata", "mirror write_neo4j_triples"]

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
Write triples
    {ANSI.green("mirror write_triples")}

---------------------------------------------
{ANSI.grey(" • ".join(commands))}"""


class Mirror:
    def scan(self, dpath: str) -> None:
        db = SqliteDatabase(DATABASE_PATH)

        photo_metadata_table = db.photo_metadata_table()
        media_metadata_table = db.media_metadata_table()
        photo_metadata_table.clean()
        media_metadata_table.clean()

        MediaScanner(dpath, db).scan()
        GeonamesScanner(db).scan()
        WikidataScanner(db).scan()

    def upload(self) -> None:
        db = SqliteDatabase(DATABASE_PATH)
        uploader = MediaUploader(db, CDN())

        uploader.upload()

    def publish(self) -> None:
        db = SqliteDatabase(DATABASE_PATH)

        builder = ArtifactBuilder(db, OUTPUT_DIRECTORY)
        builder.build()

        D1Builder(db).build()

    def read_metadata(self, content: str) -> None:
        """Read album or photo semantic information from stdin"""

        db = SqliteDatabase(DATABASE_PATH)
        read_metadata(db, content)

    def write_metadata(self, content: str) -> None:
        """Output album or photo semantic information to stdout"""

        db = SqliteDatabase(DATABASE_PATH)
        write_metadata(db, content)

    def write_triples(self) -> None:
        db = SqliteDatabase(DATABASE_PATH)
        write_neo4j_triples(db)


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
    elif command == "write_triples":
        mirror.write_triples()
    else:
        print(f"Unknown command: {command}", file=sys.stderr)
        print(doc, file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
