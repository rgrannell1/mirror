from typing import List
from src.constants import DB_PATH
from src.photo import PhotoVault, Album, Photo
from src.spaces import Spaces
from src.manifest import Manifest
from src.log import Log


def upload_thumbnail(db: Manifest, spaces: Spaces, image: Photo,
                     image_idx: int) -> None:

  Log.info(f'Checking thumbnail #{image_idx} is published for {image.path}')

  # create and upload a thumbnail
  for format in {'webp', 'jpeg'}:
    if not db.has_thumbnail(image, format):
      encoded = image.encode_thumbnail(format=format)

      thumbnail_in_spaces, thumbnail_url = spaces.thumbnail_status(
          encoded, format=format)

      if not thumbnail_in_spaces:
        Log.info(f'Uploading thumbnail #{image_idx} for {image.path}',
                 clear=True)
        spaces.upload_thumbnail(encoded, format=format)

      db.register_thumbnail_url(image, thumbnail_url, format=format)

    Log.info(f'Checking image #{image_idx} is published for {image.path}',
             clear=True)


def upload_image(db: Manifest, spaces: Spaces, image: Photo,
                 image_idx: int) -> None:

  Log.info(f'Checking image #{image_idx} is published for {image.path}',
           clear=True)

  # create an upload the image itself
  for format in {'webp', 'jpeg'}:
    if not db.has_image(image, format):
      encoded = image.encode_image(format=format)

      image_in_spaces, image_url = spaces.image_status(encoded, format=format)

      if not image_in_spaces:
        Log.info(f'Uploading #{image_idx} image for {image.path}', clear=True)
        spaces.upload_image(encoded, format=format)

      db.register_image_url(image, image_url, format=format)


def find_album_dates(db: Manifest, dir: str, images: List[Photo]) -> None:
  album = Album(dir)

  try:
    min_date = min(img.get_created_date() for img in images
                   if img.get_created_date())
    max_date = max(img.get_created_date() for img in images
                   if img.get_created_date())
  except ValueError:
    return

  if not min_date or not max_date:
    return

  min_timestamp_ms = min_date.timestamp() * 1_000
  max_timestamp_ms = max_date.timestamp() * 1_000

  db.register_dates(album.path, min_timestamp_ms, max_timestamp_ms)


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

  image_idx = 1
  published = False

  for image in db.list_publishable():
    published = True
    Log.clear()

    upload_thumbnail(db, spaces, image, image_idx)
    upload_image(db, spaces, image, image_idx)

    image_idx += 1

  if not published:
    Log.info(f'No images published', clear=True)

  Log.info(f"Finished! Publishing to {manifest_path} & {metadata_path}",
           clear=True)

  for dir, images in PhotoVault(dir, metadata_path).list_by_folder().items():
    find_album_dates(db, dir, images)

  db.create_metadata_file(manifest_path, images=True)
  db.copy_metadata_file(metadata_path, manifest_path)
