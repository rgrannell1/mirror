import base64
import os
import yaml
import json
from typing import List
from src.artifacts import AlbumArtifacts, ImagesArtifacts
from src.constants import DB_PATH, THUMBNAIL_ENCODINGS, IMAGE_ENCODINGS
from src.photo import PhotoVault, Album, Photo
from src.spaces import Spaces
from src.manifest import Manifest
from src.log import Log

def upload_thumbnail(db: Manifest, spaces: Spaces, image: Photo,
                     image_idx: int) -> None:

  Log.info(f'Checking thumbnail #{image_idx} is published for {image.path}')

  # create and upload a thumbnail
  for role, encoding_params in THUMBNAIL_ENCODINGS:
    thumbnail_format = encoding_params['format']

    if not db.has_encoded_image(image, role):
      encoded_image = image.encode_thumbnail(encoding_params)

      thumbnail_in_spaces, thumbnail_url = spaces.thumbnail_status(
          encoded_image, format=thumbnail_format)

      if not thumbnail_in_spaces:
        Log.info(f'Uploading thumbnail #{image_idx} for {image.path}',
                 clear=True)
        spaces.upload_thumbnail(encoded_image, format=thumbnail_format)

      db.add_encoded_image_url(image, thumbnail_url, role, format=thumbnail_format)

    Log.info(f'Checking image #{image_idx} is published for {image.path}',
             clear=True)


def upload_image(db: Manifest, spaces: Spaces, image: Photo,
                 image_idx: int) -> None:

  Log.info(f'Checking image #{image_idx} is published for {image.path}',
           clear=True)

  # create an upload the image itself
  for role, thumbnail_encoding in IMAGE_ENCODINGS:
    thumbnail_format = thumbnail_encoding['format']

    if not db.has_encoded_image(image, role):
      encoded = image.encode_image(thumbnail_encoding)

      image_in_spaces, image_url = spaces.image_status(encoded, format=thumbnail_format)

      if not image_in_spaces:
        Log.info(f'Uploading #{image_idx} image for {image.path}', clear=True)
        spaces.upload_image(encoded, format=thumbnail_format)

      db.add_encoded_image_url(image, image_url, role, format=thumbnail_format)


def encode_mosaic(db: Manifest, spaces: Spaces, image: Photo, image_idx: int) -> None:
  if not db.has_encoded_image(image, 'thumbnail_mosaic'):
    encoded = image.encode_image_mosaic()

    encoded_content = base64.b64encode(encoded.content).decode('ascii')
    data_url = f"data:image/bmp;base64,{encoded_content}"

    db.add_encoded_image_url(image, data_url, 'thumbnail_mosaic', 'bmp')


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

  db.add_album_dates(album.path, min_timestamp_ms, max_timestamp_ms)

def copy_metadata_file(metadata_path: str, manifest_path: str) -> None:
  """Copy the metadata file to the target destination"""

  metadata_dst = os.path.join(manifest_path, 'metadata.json')

  content = yaml.safe_load(open(metadata_path))

  with open(metadata_dst, 'w') as conn:
    conn.write(json.dumps(content))

def create_artifacts(db: Manifest, manifest_path: str) -> None:
  with open(f'{manifest_path}/albums.json', 'w') as conn:
    albums = AlbumArtifacts.content(db)
    conn.write(albums)

  with open(f'{manifest_path}/images.json', 'w') as conn:
    images = ImagesArtifacts.content(db)
    conn.write(images)

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
    encode_mosaic(db, spaces, image, image_idx)

    image_idx += 1

  if not published:
    Log.info(f'No images published', clear=True)

  Log.info(f"Finished! Publishing to {manifest_path} & {metadata_path}",
           clear=True)

  for dir, images in PhotoVault(dir, metadata_path).list_by_folder().items():
    find_album_dates(db, dir, images)

  copy_metadata_file(metadata_path, manifest_path)
  create_artifacts(db, manifest_path)
