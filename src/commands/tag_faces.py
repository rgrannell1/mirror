import face_recognition

from src.manifest import Manifest
from src.photo import PhotoVault
from src.constants import DB_PATH
from src.log import Log

def tag_faces(dir: str, metadata_path: str):
  vault = PhotoVault(dir, metadata_path)

  db = Manifest(DB_PATH, metadata_path)
  db.create()

  idx = 0
  for image in vault.list_images():
    image_path = image.path

    status = db.job_status(image, 'face_detection')
    if status == '1':
      continue

    np_image = face_recognition.load_image_file(image_path)
    face_locations = face_recognition.face_locations(np_image)

    emoji = '' if len(face_locations) == 0 else '👩'
    Log.info(f"image #{idx:,} {image_path} has {len(face_locations)} face(s) {emoji}", clear=True)

    for location in face_locations:
      db.register_faces(image, location)

    db.register_job_complete(image, 'face_detection')
    idx += 1
