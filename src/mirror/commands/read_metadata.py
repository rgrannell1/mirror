import sys
from mirror.metadata import MarkdownAlbumMetadataReader, MarkdownTablePhotoMetadataReader


def read_metadata(db, content: str) -> None:
    """Read album or photo semantic information from stdin"""

    if content not in ["photo", "album"]:
        print(f"Unknown content type: {content}", file=sys.stderr)
        return

    if content == "photo":
        photo_reader = MarkdownTablePhotoMetadataReader("/dev/stdin")

        for md in photo_reader.read_photo_metadata(db):
            fpath = db.encoded_photos_table().fpath_from_url(md.url)
            if not fpath:
                continue

            phash = db.phashes_table().phash_from_fpath(fpath)
            if not phash:
                continue

            db.photo_metadata_table().add_summary(phash, md)

    else:
        album_reader = MarkdownAlbumMetadataReader("/dev/stdin")

        db.conn.execute("delete from media_metadata_table where src_type = 'album'")

        for item in album_reader.list_album_metadata(db):
            db.conn.execute(
                """
            insert or replace into media_metadata_table (src, src_type, relation, target)
                              values (?, ?, ?, ?)
            """,
                (item.src, "album", item.relation, item.target),
            )
        db.conn.commit()
