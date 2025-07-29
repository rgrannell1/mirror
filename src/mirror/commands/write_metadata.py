import sys
from mirror.metadata import MarkdownAlbumMetadataWriter, MarkdownTablePhotoMetadataWriter


def write_metadata(db, content: str) -> None:
    """Output album or photo semantic information to stdout"""

    if content not in ["photo", "album"]:
        print(f"Unknown content type: {content}", file=sys.stderr)
        return

    if content == "photo":
        photo_writer = MarkdownTablePhotoMetadataWriter()
        photo_writer.write_photo_metadata(db)
    else:
        album_writer = MarkdownAlbumMetadataWriter()
        album_writer.write_album_metadata(db)
