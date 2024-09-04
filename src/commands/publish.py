import base64
import math
import os
import time
from urllib.parse import urlparse
import yaml
import json
from typing import List
from src.artifacts import AlbumArtifacts, ImagesArtifacts, VideoArtifacts, MetadataArtifacts
from src.constants import DB_PATH, MAX_DELETION_LIMIT, THUMBNAIL_ENCODINGS, IMAGE_ENCODINGS, VIDEO_ENCODINGS
from src.photo import PhotoVault, Album, Photo
from src.spaces import Spaces
from src.manifest import Manifest
from src.log import Log
from src.utils import deterministic_hash
from src.video import Video


def upload_thumbnail(
    db: Manifest, spaces: Spaces, image: Photo, image_idx: int
) -> None:
    Log.info(f"Checking thumbnail #{image_idx} is published for {image.path}")

    # create and upload a thumbnail
    for role, encoding_params in THUMBNAIL_ENCODINGS:
        thumbnail_format = encoding_params["format"]

        if not db.has_encoded_image(image, role):
            encoded_image = image.encode_thumbnail(encoding_params)

            thumbnail_in_spaces, thumbnail_url = spaces.thumbnail_status(
                encoded_image, format=thumbnail_format
            )

            if not thumbnail_in_spaces:
                Log.info(
                    f"Uploading thumbnail #{image_idx} for {image.path}", clear=True
                )
                spaces.upload_thumbnail(encoded_image, format=thumbnail_format)

            db.add_encoded_image_url(
                image, thumbnail_url, role, format=thumbnail_format
            )

        Log.info(
            f"Checking image #{image_idx} is published for {image.path}", clear=True
        )


def upload_image(db: Manifest, spaces: Spaces, image: Photo, image_idx: int) -> None:
    Log.info(f"Checking image #{image_idx} is published for {image.path}", clear=True)

    # create an upload the image itself
    for role, thumbnail_encoding in IMAGE_ENCODINGS:
        thumbnail_format = thumbnail_encoding["format"]

        if not db.has_encoded_image(image, role):
            encoded = image.encode_image(thumbnail_encoding)

            image_in_spaces, image_url = spaces.image_status(
                encoded, format=thumbnail_format
            )

            if not image_in_spaces:
                Log.info(f"Uploading #{image_idx} image for {image.path}", clear=True)
                spaces.upload_image(encoded, format=thumbnail_format)

            db.add_encoded_image_url(image, image_url, role, format=thumbnail_format)


def upload_video(db: Manifest, spaces: Spaces, video: Video, image_idx: int) -> None:
    Log.info(f"Checking video #{image_idx} is published for {video.path}")

    for role, encoding_params in VIDEO_ENCODINGS:
        bitrate = encoding_params["bitrate"]
        width = encoding_params["width"]
        height = encoding_params["height"]

        share_audio = video.get_xattr_share_audio()

        upload_file_name = Spaces.video_name(video.path, bitrate, width, height)
        video_in_spaces, video_url = spaces.video_status(upload_file_name)

        if not video_in_spaces:
            Log.info(f"Uploading video #{image_idx} for {video.path}", clear=True)
            encoded_video_path = video.encode_video(bitrate, width, height, share_audio)
            spaces.upload_file_public(upload_file_name, encoded_video_path)

        db.add_encoded_video_url(video, video_url, role)


def encode_thumbnail_data_url(db: Manifest, image: Photo, image_idx: int) -> None:
    if not db.has_encoded_image(image, "thumbnail_mosaic"):
        encoded = image.encode_image_mosaic()

        encoded_content = base64.b64encode(encoded.content).decode("ascii")
        data_url = f"data:image/bmp;base64,{encoded_content}"

        db.add_encoded_image_url(image, data_url, "thumbnail_mosaic", "bmp")


def find_album_dates(db: Manifest, dir: str, images: List[Photo]) -> None:
    album = Album(dir)

    try:
        min_date = min(
            img.get_created_date() for img in images if img.get_created_date()
        )
        max_date = max(
            img.get_created_date() for img in images if img.get_created_date()
        )
    except ValueError:
        return

    if not min_date or not max_date:
        return

    min_timestamp_ms = min_date.timestamp() * 1_000
    max_timestamp_ms = max_date.timestamp() * 1_000

    db.add_album_dates(album.path, min_timestamp_ms, max_timestamp_ms)


def copy_metadata_file(metadata_path: str, manifest_path: str) -> None:
    """Copy the metadata file to the target destination"""

    metadata_dst = os.path.join(manifest_path, "metadata.json")

    content = yaml.safe_load(open(metadata_path))

    with open(metadata_dst, "w") as conn:
        conn.write(json.dumps(content))


def create_artifacts(db: Manifest, manifest_path: str) -> None:
    publication_id = deterministic_hash(str(math.floor(time.time())))

    # clear existing albums and images

    removeable = [
        file
        for file in os.listdir(manifest_path)
        if file.startswith(("albums", "images"))
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
        conn.write(json.dumps(md))


def publish_images(db, spaces):
    image_idx = 1

    for image in db.list_publishable_images():
        Log.clear()

        upload_thumbnail(db, spaces, image, image_idx)
        upload_image(db, spaces, image, image_idx)
        encode_thumbnail_data_url(db, image, image_idx)

        image_idx += 1


def publish_videos(db, spaces):
    video_idx = 1

    for video in db.list_publishable_videos():
        Log.clear()

        upload_video(db, spaces, video, video_idx)
        video_idx += 1


def remove_unpublished_media(db, spaces):
    """Remove artifacts from the Spaces bucket that are no longer published, to allow
    unpublishing"""

    published_media = set(spaces.list_objects())

    currently_published = {urlparse(url).path[1:] for url in db.list_media_urls()}
    to_delist = published_media - currently_published

    if len(to_delist) > MAX_DELETION_LIMIT:
        raise Exception("Too many files to delist, simply refusing! Fix your code!")

    for file in to_delist:
        spaces.delete_object(file)


def publish(dir: str, metadata_path: str, manifest_path: str):
    """List all images tagged with 'Published'. Find what images are already published,
    and compute a minimal set of optimised Webp images and thumbnails to publish. Publish
    the images to DigitalOcean Spaces.
    """

    db = Manifest(DB_PATH, metadata_path)
    db.create()

    spaces = Spaces()
    spaces.set_bucket_acl()
    spaces.set_bucket_cors_policy()

    publish_images(db, spaces)
    publish_videos(db, spaces)

    Log.info(f"Finished! Publishing to {manifest_path} & {metadata_path}", clear=True)

    for dir, dir_data in PhotoVault(dir, metadata_path).list_by_folder().items():
        images = dir_data["images"]

        find_album_dates(db, dir, images)

    create_artifacts(db, manifest_path)
    remove_unpublished_media(db, spaces)
