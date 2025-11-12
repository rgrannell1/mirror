import json
import tomllib
from typing import Iterator
from mirror.data.types import SemanticTriple


class UnescoReader:
    places_file: str
    data_file: str

    def __init__(self, places_file: str = "places.toml", data_file: str = "src/data/whc001.json"):
        self.places_file = places_file
        self.data_file = data_file

    def read(self, db: "SqliteDatabase") -> Iterator[SemanticTriple]:

      unesco_ids = set()

      with open(self.places_file, 'rb') as conn:
          places = tomllib.load(conn)

      for place in places['places']:
          unesco_urn = place.get("unesco_id")

          if unesco_urn:
              id = unesco_urn.split(":")[-1]
              unesco_ids.add(id)

      unesco_data = json.load(open(self.data_file, "r", encoding="utf-8"))

      for unesco_site in unesco_data:
          id_no = unesco_site['id_no']
          if id_no not in unesco_ids:
              continue

          urn = f"urn:ró:unesco:{id_no}"

          yield SemanticTriple(
              source=urn,
              relation="name",
              target=unesco_site['name_en'],)

          yield SemanticTriple(
              source=urn,
              relation="longitude",
              target=unesco_site['coordinates']['lon'],)

          yield SemanticTriple(
              source=urn,
              relation="latitude",
              target=unesco_site['coordinates']['lat'],)
