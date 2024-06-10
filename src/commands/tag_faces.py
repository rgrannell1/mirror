from multiprocessing import Pool, cpu_count
import re
from typing import List, Tuple
import face_recognition

from src.manifest import Manifest
from src.photo import PhotoVault, Photo
from src.constants import DB_PATH
from src.log import Log

PROCESS_COUNT = cpu_count() - 1


def chunker(seq, size):
  return (seq[pos:pos + size] for pos in range(0, len(seq), size))


def tag_faces_in_image(args) -> Tuple[Photo, List[Tuple[int, int, int, int]]]:
  """Tag faces in the given image."""

  image, idx, total = args
  image_path = image.path

  try:
    np_image = face_recognition.load_image_file(image_path)
    face_locations = face_recognition.face_locations(np_image)
  except BaseException:
    return image, []

  emoji = '' if len(face_locations) == 0 else '👩'
  Log.info(
      f"image {image_path} has {len(face_locations)} face(s) {emoji} ({idx:,} / {total:,})",
      clear=True)

  return image, face_locations


def tag_faces(dir: str, metadata_path: str, exclude: str):
  """Tag faces in the given directory."""

  vault = PhotoVault(dir, metadata_path)

  db = Manifest(DB_PATH, metadata_path)
  db.create()

  pool = Pool(processes=PROCESS_COUNT)

  filtered_images = [
      image for image in vault.list_images()
      if not db.job_status(image, 'face_detection') and (
          not exclude or not re.search(exclude, image.path))
  ]

  target_images = [(image, idx) for idx, image in enumerate(filtered_images)]

  for images in chunker(target_images, PROCESS_COUNT):
    inputs = {(image, idx, len(target_images)) for image, idx in images}
    results = pool.map_async(tag_faces_in_image, inputs).get()

    for image, face_locations in results:
      for location in face_locations:
        db.register_faces(image, location)

      db.register_job_complete(image, 'face_detection')
