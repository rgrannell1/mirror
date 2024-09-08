"""Classes for dealing with tag-files, and tag metadata-files"""

import yaml
from queue import Queue
from typing import List

cache = {}


class Tags:
    """Represents a tag metadata file, which provides a tree of subsumptions
    describing tags and their parents"""

    fpath: str

    def __init__(self, fpath: str) -> None:
        self.fpath = fpath

        if fpath not in cache:
            with open(fpath) as conn:
                cache[fpath] = yaml.safe_load(conn)

        self.tag_tree = cache[fpath]

    def expand(self, tags: List) -> List[str]:
        """Given a list of tags, expand them to include their parents, and return"""

        expanded_tags = set()
        queue: Queue[str] = Queue()

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
