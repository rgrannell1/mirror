"""The core logic of mirror. This is the entrypoint for the CLI, and
   contains the logic for each command."""

from src.photo import PhotoVault
from src.tags import Tagfile
from src.manifest import Manifest

def init(dir: str):
  """Create tags.md files in each photo-directory, with information
     extracted from extended-attributes. Create a manifest"""

  for dirname, images in PhotoVault(dir).list_by_folder().items():
    Tagfile(dirname, images).write()

  db = Manifest()
  db.create()

  for image in PhotoVault(dir).list_images():
    db.add_image(image)

  for album in PhotoVault(dir).list_albums():
    md = album.get_metadata()

    if not md:
      continue

    db.add_album(md)
