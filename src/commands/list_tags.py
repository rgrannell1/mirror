import json

from src.photo import PhotoVault
from src.constants import ATTR_TAG
from src.tags import Tags


def list_tags(dir: str, opts):
  """List all tags in all images in the directory, as a series
         of JSON objects"""
  tag_set = {}

  graphvis = opts['graphvis']
  metadata_path = opts['metadata']

  for image in PhotoVault(dir, metadata_path).list_images():
    tags = image.get_metadata()

    if ATTR_TAG not in tags:
      continue

    for tag in tags[ATTR_TAG]:
      if tag not in tag_set:
        tag_set[tag] = 1

      tag_set[tag] += 1

  if graphvis:
    graph = ['graph tags {', '  layout="fdp"']
    vars = {}

    idx = 0
    for tag in Tags(metadata_path).expand(tag_set.keys()):
      if not tag:
        continue

      var_name = f'n{idx}'
      vars[tag] = var_name

      graph += [f'    {var_name}[label="{tag}"];']
      idx += 1

    tree = Tags(metadata_path).tag_tree

    for parent, children in tree.items():
      parent_var = vars[parent]
      for child in children:

        if child in vars:
          child_var = vars[child]
          graph += [f'    {parent_var} -- {child_var};']

    graph += ['}']

    print('\n'.join(graph))
    return

  for tag, count in tag_set.items():
    if tag == '':
      continue

    print(json.dumps({'tag': tag, 'count': count}))
