import math
import os
import re
import sys
import json
import time
from typing import Dict, List, Protocol
import markdown
from src.manifest import Manifest
from src.utils import deterministic_hash

IMAGES_HEADERS = [
    "fpath",
    "id",
    "album_id",
    "tags",
    "description",
    "date_time",
    "f_number",
    "focal_length",
    "model",
    "iso",
    "blur",
    "shutter_speed",
    "width",
    "height",
    "thumbnail_url",
    "thumbnail_data_url",
    "image_url",
    "rating",
    "subject",
]

VIDEO_HEADERS = [
    "fpath",
    "id",
    "album_id",
    "tags",
    "description",
    "video_url_unscaled",
    "video_url_1080p",
    "video_url_720p",
    "video_url_480p",
    "poster_url",
]

ALBUMS_HEADERS = [
    "id",
    "album_name",
    "min_date",
    "max_date",
    "description",
    "image_count",
    "thumbnail_url",
    "thumbnail_mosaic_url",
    "flags",
]

class IArtifact(Protocol):
    @staticmethod
    def content(db: Manifest) -> str:
        pass

class ImagesArtifacts(IArtifact):
    """Generate an artifact describing the images in the database."""

    @staticmethod
    def content(db: Manifest) -> str:
        cursor = db.conn.cursor()
        cursor.execute("select * from images_artifact")

        rows = [IMAGES_HEADERS]

        for row in cursor.fetchall():
            fpath, album_permalink, tags, tags_v2, description, *rest = row

            if not album_permalink:
                raise ValueError(
                    f"did not find a permalink for album '{fpath}'. Please update {fpath}/tags.md"
                )

            joined_tags = {
                tag.strip()
                for tag in re.split(r"\s*,\s*", tags if tags else "")
                + re.split(r"\s*,\s*", tags_v2 if tags_v2 else "")
                if tag
            }

            rows.append(
                [
                    fpath,
                    deterministic_hash(fpath),
                    album_permalink,
                    ",".join(joined_tags),
                    markdown.markdown(description),
                ]
                + rest
            )

        return json.dumps(rows)


class VideoArtifacts(IArtifact):
    @staticmethod
    def content(db: Manifest) -> str:
        cursor = db.conn.cursor()
        cursor.execute("select * from videos_artifact")
        rows = [VIDEO_HEADERS]

        for row in cursor.fetchall():
            fpath, album_permalink, *rest = row

            if not album_permalink:
                raise ValueError(
                    f"did not find a permalink for image '{fpath}'. Please update {fpath}/tags.md"
                )

            rows.append(
                [
                    fpath,
                    deterministic_hash(fpath),
                    album_permalink,
                ]
                + rest
            )

        return json.dumps(rows)


class AlbumArtifacts(IArtifact):
    """Generate an artifact describing the albums in the database."""

    @staticmethod
    def content(db: Manifest) -> str:
        cursor = db.conn.cursor()
        cursor.execute("select * from albums_artifact")

        messages = []
        rows = [ALBUMS_HEADERS]

        for row in cursor.fetchall():
            if not row[0]:
                messages.append(
                    f"did not find a permalink for album '{row[1]}'. Please update {row[0]}/tags.md"
                )
                continue

            if not row[6]:
                messages.append(
                    f"did not find a cover image for album '{row[1]}'. Please update {row[0]}/tags.md"
                )
                continue

            permalink, album_name, min_date, max_date, description, *rest = row

            rows.append(
                [
                    permalink,
                    album_name,
                    min_date,
                    max_date,
                    markdown.markdown(description),
                ]
                + rest
            )

        if messages:
            print("\n".join(messages), file=sys.stderr)

        return json.dumps(rows)


class MetadataArtifacts(IArtifact):
    @staticmethod
    def get_subsumed(db: Manifest, is_a: str) -> List[str]:
        cursor = db.conn.cursor()
        cursor.execute(
            """
    select distinct(source) from photo_relations
      where relation = 'is-a' and target = ?
      order by source;
    """,
            (is_a,),
        )

        children = set()

        for row in cursor.fetchall():
            sources = row[0].split(",")
            for source in sources:
                children.add(source)

        return sorted(list(children))

    @staticmethod
    def content(db: Manifest) -> str:
        return json.dumps({
            "Bird": {"children": MetadataArtifacts.get_subsumed(db, "Bird")},
            "Plane": {"children": MetadataArtifacts.get_subsumed(db, "Plane")},
            "Helicopter": {
                "children": MetadataArtifacts.get_subsumed(db, "Helicopter")
            },
            "Mammal": {"children": MetadataArtifacts.get_subsumed(db, "Mammal")},
        })


def create_artifacts(db: Manifest, manifest_path: str) -> None:
    publication_id = deterministic_hash(str(math.floor(time.time())))

    # clear existing albums and images

    removeable = [
        file
        for file in os.listdir(manifest_path)
        if file.startswith(("albums", "images", "videos"))
    ]

    for file in removeable:
        os.remove(f"{manifest_path}/{file}")

    # create new albums and images
    with open(f"{manifest_path}/albums.{publication_id}.json", "w") as conn:
        albums = AlbumArtifacts.content(db)
        conn.write(albums)

    with open(f"{manifest_path}/images.{publication_id}.json", "w") as conn:
        images = ImagesArtifacts.content(db)
        conn.write(images)

    with open(f"{manifest_path}/videos.{publication_id}.json", "w") as conn:
        images = VideoArtifacts.content(db)
        conn.write(images)

    with open(f"{manifest_path}/env.json", "w") as conn:
        conn.write(json.dumps({"publication_id": publication_id}))

    with open(f"{manifest_path}/metadata.json", "w") as conn:
        md = MetadataArtifacts.content(db)
        conn.write(md)
