
import os
import yaml
import shutil
import datetime

from src.constants import ATTR_TAG

def tag_tree(tree):
  expanded = {}

  for parent_tag, children_tags in tree.items():
    if parent_tag not in expanded:
      expanded[parent_tag] = set()

    for child_tag in children_tags:
      if child_tag not in expanded:
        expanded[child_tag] = set()

      expanded[child_tag].add(parent_tag)

  return expanded

class TagMetadata:
  def __init__(self, fpath) -> None:
    self.fpath = fpath

    with open(fpath) as conn:
      self.tag_tree = tag_tree(yaml.safe_load(conn))

  def add_tags(self, tag: str):
    tags = set([tag])

    return [tag]

class Tagfile:
  def __init__(self, dirname: str, images) -> None:
    self.dirname = dirname
    self.images = images

  def content(self) -> str:
    notes = ""
    notes += f"# {self.dirname}\n"
    notes += "\n"

    for image in self.images:
      name = image.name()

      notes += f"## {name}\n\n"
      notes += f"![{name}]({name})\n\n"
      notes += f"{ATTR_TAG}\n"

      attrs = image.get_metadata()

      if ATTR_TAG in attrs:
        for tag in attrs[ATTR_TAG]:
          notes += f"- {tag}\n"

      notes += "\n"

    return notes

  def write(self) -> None:
    content = self.content()
    tag_path = f"{self.dirname}/tags.md"

    if os.path.exists(tag_path):
      now = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

      new_tag_path = f"{tag_path}-{now}"
      shutil.move(tag_path, new_tag_path)

    with open(tag_path, "w") as conn:
      conn.write(content)

  @classmethod
  def read(kls, fpath):
    current_image = None
    current_tags = []

    with open(fpath, 'r') as conn:
      for line in conn.readlines():
        if line.startswith('## '):
          current_image = line[3:].strip()

          if current_tags:
            yield {
              'dpath': os.path.dirname(fpath),
              'fpath': os.path.join(os.path.dirname(fpath), current_image),
              'fname': current_image,
              'attrs': {
                ATTR_TAG: ', '.join(current_tags)
              }
            }

          current_tags = []

        if line.startswith('-'):
          tag = line[1:].strip()
          current_tags.append(tag)
