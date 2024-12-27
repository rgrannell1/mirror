import sys
from src.ansi import ANSI
from src.artifacts import ArtifactBuilder
from src.cdn import CDN
from src.config import DATABASE_PATH, OUTPUT_DIRECTORY, PHOTO_DIRECTORY
from src.database import SqliteDatabase
from src.uploader import MediaUploader
from src.scanner import MediaScanner, LinnaeusScanner

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
{ANSI.grey(' • '.join(commands))}"""


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


if __name__ == "__main__":
    main()
