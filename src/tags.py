"""Classes for dealing with tag-files, and tag metadata-files"""

import yaml
from queue import Queue


class Tags:
  """Represents a tag metadata file, which provides a tree of subsumptions
     describing tags and their parents"""
  def __init__(self, fpath) -> None:
    self.fpath = fpath

    # convert the tag metadata into a tag-tree
    with open(fpath) as conn:
      self.tag_tree = yaml.safe_load(conn)

  def expand(self, tags):
    expanded_tags = set()
    queue = Queue()

    for tag in tags:
      queue.put(tag)

    while not queue.empty():
      tag = queue.get()
      expanded_tags.add(tag)

      for parent_tag, children_tags in self.tag_tree.items():
        if tag in children_tags:
          queue.put(parent_tag)
          expanded_tags.add(parent_tag)

    return list(expanded_tags)
