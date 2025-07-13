import sys
from src.metadata import MarkdownAlbumMetadataReader, MarkdownTablePhotoMetadataReader


def read_metadata(db, content: str) -> None:
    """Read album or photo semantic information from stdin"""

    if content not in ["photo", "album"]:
        print(f"Unknown content type: {content}", file=sys.stderr)
        return

    if content == "photo":
        md_reader = MarkdownTablePhotoMetadataReader("/dev/stdin")

        db.write_photo_metadata(md_reader.read_photo_metadata(db))
    else:
        md_reader = MarkdownAlbumMetadataReader("/dev/stdin")

        db.write_album_metadata(md_reader.list_album_metadata(db))
