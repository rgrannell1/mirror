from src.constants import DB_PATH
from src.photo import PhotoVault, Photo
from src.tagfile import Tagfile
from src.manifest import Manifest
from src.log import Log
from src.video import Video


def set_images_metadata(vault: PhotoVault, metadata_path: str):
    idx = 0
    images = vault.list_tagfile_image()

    # set metadata on each image mentioned in a tagfile
    for entry in images:
        Log.info(
            f"setting xattr metadata on photo {idx:,} / {len(images):,}", clear=True
        )

        Photo(entry.fpath, metadata_path).set_metadata(entry.attrs, entry.album)
        idx += 1


def set_videos_metadata(vault: PhotoVault, metadata_path: str):
    """set metadata (non-exif in this case) for videos"""
    idx = 0
    # broken; only two videos are listed in the tagfiles?
    # but there is stuff in the tagfiles
    videos = vault.list_tagfile_video()

    # set metadata on each video mentioned in a tagfile
    for entry in videos:
        Log.info(
            f"setting xattr metadata on video {idx:,} / {len(videos):,}", clear=True
        )

        Video(entry.fpath, metadata_path).set_metadata(entry.attrs, entry.album)
        idx += 1


def tag(dpath: str, metadata_path: str):
    """Read tags.md files in each photo-directory, and write extended
    attributes to each image"""

    db = Manifest(DB_PATH, metadata_path)
    db.create()

    vault = PhotoVault(dpath, metadata_path)

    set_images_metadata(vault, metadata_path)
    set_videos_metadata(vault, metadata_path)

    idx = 0
    by_folder = PhotoVault(dpath, metadata_path).list_by_folder().items()

    # update the tagfiles in each folder based on the newly written metadata
    for dirname, dir_data in by_folder:
        images = dir_data["images"]
        videos = dir_data["videos"]

        Log.info(f"writing tagfile {idx} / {len(by_folder)}", clear=True)
        idx += 1

        Tagfile(dirname, metadata_path, images, videos).write()

    Log.info("updating database", clear=True)

    # add every image to the sqlite database
    for image in vault.list_images():
        db.add_image(image)

    # add every video to the sqlite database
    for video in vault.list_videos():
        db.add_video(video)

    for album in vault.list_albums():
        album_md = album.get_metadata()

        if album_md:
            db.add_album(album_md)

    Log.info("Tagging complete", clear=True)
