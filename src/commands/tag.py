
from src.photo import PhotoVault, Photo
from src.tags import TagMetadata

def tag(dir: str, metadata_path: str):
  """Read tags.md files in each photo-directory, and write extended
     attributes to each image"""

  photo_dir = PhotoVault(dir)
  tag_metadata = TagMetadata(metadata_path)

  for entry in photo_dir.list_tagfiles():
    fpath = entry['fpath']
    attrs = entry['attrs']
    album = entry['album']

    Photo(fpath).set_metadata(attrs, album, tag_metadata)
