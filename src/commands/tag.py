from src.constants import DB_PATH
from src.photo import PhotoVault, Photo
from src.tags import Tags
from src.tagfile import Tagfile
from src.manifest import Manifest
from src.log import Log


def tag(dir: str, metadata_path: str):
  """Read tags.md files in each photo-directory, and write extended
             attributes to each image"""

  db = Manifest(DB_PATH, metadata_path)
  db.create()

  vault = PhotoVault(dir, metadata_path)

  idx = 0
  images = vault.list_tagfile_image()

  # set metadata on each image mentioned in a tagfile
  for entry in images:
    Log.info(f"setting xattr metadata on photo {idx:,} / {len(images):,}",
             clear=True)

    Photo(entry.fpath, metadata_path).set_metadata(entry.attrs, entry.album)
    idx += 1

  idx = 0
  by_folder = PhotoVault(dir, metadata_path).list_by_folder().items()

  # update the tagfiles in each folder based on the newly written metadata
  for dirname, images in by_folder:
    Log.info(f"writing tagfile {idx} / {len(by_folder)}", clear=True)
    idx += 1

    Tagfile(dirname, metadata_path, images).write()

  Log.info(f"updating database", clear=True)

  # add every image to the sqlite database
  for image in vault.list_images():
    db.add_image(image)

  for album in vault.list_albums():
    album_md = album.get_metadata()

    if not album_md:
      continue

    db.add_album(album_md)
