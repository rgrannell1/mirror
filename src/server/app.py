"""Serve a website for viewing photographs & setting tag information"""

import json
from flask import Flask, send_file, jsonify

from src.photo import PhotoVault

PHOTO_DIR = "/home/rg/Drive/Photos"
PHOTO_METADATA_PATH = "/home/rg/Drive/Photos/metadata.yaml"

vault = PhotoVault(PHOTO_DIR, PHOTO_METADATA_PATH)
images = vault.list_images()

app = Flask(__name__,
  static_folder='static',
  static_url_path='')

### ++++++++++ PHOTO ++++++++++ ###
### ++++++++++       ++++++++++ ###

@app.route('/photo/<id>')
def get_photo(id):
    """Return the next photo, using some sort of ordering"""
    image_path = images[int(id)].path
    return send_file(image_path)

@app.route('/photo/random')
def random_photo():
  """Return a random photo"""
  pass

@app.route('/photo/<id>/metadata', methods=['GET'])
def get_photo_metadata(id):
  """Update metadata for a photo"""

  image = images[int(id)]
  return jsonify(
    tags=image.tags(),
    path=image.path,
    id=id
  )
