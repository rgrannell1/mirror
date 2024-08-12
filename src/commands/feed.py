import json
import os

from src.constants import DB_PATH
from src.manifest import Manifest
from src.syndications import JSONFeed
from collections import defaultdict


def feed(dir: str, metadata_path: str, out_dir: str):
  """Generates a JSON feed for the given directory."""

  image_by_tags = defaultdict(list)
  all_images = []

  db = Manifest(DB_PATH, metadata_path)

  for image in db.list_publishable():
    all_images.append(image)

    if not image.exists():
      continue

    tags = image.tags()

    if 'Published' not in tags:
      continue

    for tag in tags:
      image_by_tags[tag].append(image)

  # write each tag feed
  for tag, images in image_by_tags.items():
    if tag == 'Published':
      continue

    feed = JSONFeed.tag_feed(db, tag, images)

    os.makedirs(f'{out_dir}/tags', exist_ok=True)

    with open(f'{out_dir}/tags/{tag}.json', 'w') as conn:
      conn.write(json.dumps(feed, indent=2, ensure_ascii=False))

  # write a root feed
  for image in all_images:
    feed = JSONFeed.feed(db, images)

    with open(f'{out_dir}/index.json', 'w') as conn:
      conn.write(json.dumps(feed, indent=2, ensure_ascii=False))
