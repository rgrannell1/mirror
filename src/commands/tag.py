
from src.photo import PhotoVault, Photo
from src.tags import Tags
from src.commands.init import init

def tag(dir: str, metadata_path: str):
  """Read tags.md files in each photo-directory, and write extended
     attributes to each image"""

  vault = PhotoVault(dir)
  tag_metadata = Tags(metadata_path)

  # set metadata on each image
  for entry in vault.list_tagfile_image():
    fpath = entry['fpath']
    attrs = entry['attrs']
    album = entry['album']

    Photo(fpath).set_metadata(attrs, album, tag_metadata)

  # re-initialise
  init(dir)
