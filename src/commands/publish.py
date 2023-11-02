
import sys

from src.photo import PhotoVault, Album
from src.spaces import Spaces
from src.manifest import Manifest

def publish(dir: str, manifest_path: str):
  """List all images tagged with 'Published'. Find what images are already published,
  and compute a minimal set of optimised Webp images and thumbnails to publish. Publish
  the images to DigitalOcean Spaces.
  """

  db = Manifest()
  db.create()

  spaces = Spaces()
  spaces.set_bucket_acl()
  spaces.set_bucket_cors_policy()

  published = False

  for image in db.list_publishable():
    published = True
    print(f'Checking thumbnail for {image.path}', file=sys.stderr)

    # create and upload a thumbnail
    if not db.has_thumbnail(image):
      encoded = image.encode_thumbnail()

      thumbnail_in_spaces, thumbnail_url = spaces.thumbnail_status(encoded)

      if not thumbnail_in_spaces:
        spaces.upload_thumbnail(encoded)
        print(f'Uploaded thumbnail for {image.path}', file=sys.stderr)

      db.register_thumbnail_url(image, thumbnail_url)

    print(f'Checking image for {image.path}', file=sys.stderr)

    # create an upload the image itself
    if not db.has_image(image):
      encoded = image.encode_image()

      image_in_spaces, image_url = spaces.image_status(encoded)

      if not image_in_spaces:
        spaces.upload_image(encoded)
        print(f'Uploaded image for {image.path}', file=sys.stderr)

      db.register_image_url(image, image_url)

  if not published:
    print('No images published', file=sys.stderr)

  for dir, images in PhotoVault(dir).list_by_folder().items():
    album = Album(dir)

    try:
      min_date = min(img.get_created_date() for img in images if img.get_created_date())
      max_date = max(img.get_created_date() for img in images if img.get_created_date())
    except ValueError:
      pass

    if not min_date or not max_date:
      continue

    min_timestamp_ms = min_date.timestamp() * 1_000
    max_timestamp_ms = max_date.timestamp() * 1_000

    db.register_dates(album.path, min_timestamp_ms, max_timestamp_ms)

  db.create_metadata_file(manifest_path)
