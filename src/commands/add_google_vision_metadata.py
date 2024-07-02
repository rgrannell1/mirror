
from typing import List
from google.cloud import vision

from src.constants import DB_PATH
from src.manifest import Manifest
from src.photo import Photo

class GoogleVision:
  def __init__(self):
    self.client = vision.ImageAnnotatorClient()

  def analyse_image(self, photo: Photo, features: List):
    with open(photo.path, 'rb') as conn:
      request = vision.AnnotateImageRequest(
        image=vision.Image(content=conn.read()),
        features=features)

      return self.client.annotate_image(request=request)

def add_google_vision_metadata(dir: str, metadata_path: str):
  google_vision = GoogleVision()

  vision_features = [
    vision.Feature(type_=vision.Feature.Type.LABEL_DETECTION)
  ]

  db = Manifest(DB_PATH, metadata_path)
  db.create()

  for image in db.list_publishable():
    if db.has_google_labels(image.path):
      continue

    print(f"Analysing {image.path}")

    res = google_vision.analyse_image(image, vision_features)

    labels = [
      {
        "fpath": image.path,
        "mid": label.mid,
        "description": label.description,
        "score": label.score,
        "topicality": label.topicality
      }
      for label in res.label_annotations
    ]

    db.add_google_labels(image.path, labels)
