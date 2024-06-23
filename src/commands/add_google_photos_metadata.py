
import re
import json
from src.constants import DB_PATH
from src.manifest import Manifest


def add_google_photos_metadata(dir: str, metadata_path: str, google_photos_file: str):
  db = Manifest(DB_PATH, metadata_path)
  db.create()

  for image in json.load(open(google_photos_file)):
    if not 'href' in image:
      continue

    matches = re.search(r'(?P<lat>[-]?\d+\.\d+),(?P<lon>[-]\d+\.\d+)', image['href'])
    if not matches:
      continue

    lat = matches.group('lat')
    lon = matches.group('lon')

    tidy_address = (
      image.get('location', '')
      .replace('Add a location', ""))

    tidy_address = re.sub("Estimated location.+Learn more", "", tidy_address)

    db.add_google_photos_metadata(image['fpath'], tidy_address, lat, lon)
