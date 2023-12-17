
from src.photo import PhotoVault, Photo
from src.tags import TagMetadata
from src.commands.init import init

def tag(dir: str, metadata_path: str):
  """Read tags.md files in each photo-directory, and write extended
     attributes to each image"""

  vault = PhotoVault(dir)
  tag_metadata = TagMetadata(metadata_path)

  # set metadata on each image
  for entry in vault.list_tagfiles():
    fpath = entry['fpath']
    attrs = entry['attrs']
    album = entry['album']

    Photo(fpath).set_metadata(attrs, album, tag_metadata)

  # re-initialise
  init(dir)
