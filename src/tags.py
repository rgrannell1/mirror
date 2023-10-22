"""Classes for dealing with tag-files, and tag metadata-files"""

import os
import yaml
import shutil
import datetime

from src.constants import ATTR_TAG

def tag_tree(tree):
  """Expand a tag-tree so that subsumptions can be easily accessed"""
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
  """Represents a tag metadata file, which provides a tree of subsumptions
     describing tags and their parents"""
  def __init__(self, fpath) -> None:
    self.fpath = fpath

    # convert the tag metadata into a tag-tree
    with open(fpath) as conn:
      self.tag_tree = tag_tree(yaml.safe_load(conn))

  # TODO this needs work
  def add_tags(self, tag: str):
    tags = set([tag])

    return [tag]

class Tagfile:
  """Represents a Tagfile in a directory of images"""

  def __init__(self, dirname: str, images) -> None:
    self.dirname = dirname
    self.images = images

  def content(self) -> str:
    """Given a series of images, and a directory, return the content of a tagfile."""

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
    """Write a tagfile to the current directory."""
    content = self.content()
    tag_path = f"{self.dirname}/tags.md"

    # backup any existing tagfile
    if os.path.exists(tag_path):
      now = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

      new_tag_path = f"{tag_path}-{now}"
      shutil.move(tag_path, new_tag_path)

    # write the tagfile content to the directory
    with open(tag_path, "w") as conn:
      conn.write(content)

  @classmethod
  def read(kls, fpath):
    """Read a tagfile, and yield each image and its associated tags."""
    current_image = None
    current_tags = []

    with open(fpath, 'r') as conn:
      for line in conn.readlines():
        if line.startswith('## '):
          # a heading indicates a new image is being processed
          current_image = line[3:].strip()

          # if current tags is defined, yield image information and attributes
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

        # if a line starts with a dash, it's a tag
        # append them to the current tags
        if line.startswith('-'):
          tag = line[1:].strip()
          current_tags.append(tag)
