

import tomllib
from typing import Iterator
from pathlib import Path

from mirror.data.types import SemanticTriple


class ThingsReader:
  """Read general things information from a things.toml file"""

  def __init__(self, things_file: str = "things.toml"):
    self.things_file = things_file

  def to_triples(self, item: dict) -> Iterator[SemanticTriple]:
    src = item['id']

    for relation in item.keys():
      tgt_vals = item[relation]

      if isinstance(tgt_vals, list):
        for val in tgt_vals:
          yield SemanticTriple(
            source=src,
            relation=relation,
            target=val
          )
      else:
        yield SemanticTriple(
          source=src,
          relation=relation,
          target=tgt_vals
        )

  def read(self, db) -> Iterator[SemanticTriple]:
    """Read TOML information and yield semantic triples"""

    things_path = Path(self.things_file)

    if not things_path.exists():
      return

    with open(things_path, 'rb') as conn:
      data = tomllib.load(conn)

    # TODO validate these against a schema based on type
    for urn_info in data.values():
      for item in urn_info:
        yield from self.to_triples(item)
