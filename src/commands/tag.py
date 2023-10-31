
from src.photo import PhotoVault, Photo
from src.tags import TagMetadata
from src.manifest import Manifest

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

  db = Manifest()

  for image in PhotoVault(dir).list_images():
    db.add_image(image)

  for album in PhotoVault(dir).list_albums():
    md = album.get_metadata()

    if not md:
      continue

    db.add_album(md)
