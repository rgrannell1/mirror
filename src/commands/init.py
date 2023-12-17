"""The core logic of mirror. This is the entrypoint for the CLI, and
   contains the logic for each command."""

from src.photo import PhotoVault
from src.tagfile import Tagfile
from src.manifest import Manifest

def init(dir: str, metadata_path: str):
  """Create tags.md files in each photo-directory, with information
     extracted from extended-attributes. Create a manifest"""

  for dirname, images in PhotoVault(dir).list_by_folder().items():
    Tagfile(dirname, metadata_path, images).write()

  vault = PhotoVault(dir)
  db = Manifest()
  db.create()


  # add every image to the sqlite database
  for image in vault.list_images():
    db.add_image(image)

  for album in vault.list_albums():
    md = album.get_metadata()

    if not md:
      continue

    db.add_album(md)
