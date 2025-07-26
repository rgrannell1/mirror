import json
from typing import Any, Iterator
from attr import dataclass
import requests

from src.constants import KnownWikiProperties
from src.data.types import SemanticTriple


class WikidataClient:
    SPARQL_ENDPOINT = "https://query.wikidata.org/sparql"
    API_ENDPOINT = "https://www.wikidata.org/w/api.php"

    def get_by_id(self, id: str) -> dict | None:
        """Fetches full entity data from Wikidata by QID."""
        url = f"{self.API_ENDPOINT}?action=wbgetentities&ids={id}&format=json&languages=en"
        response = requests.get(url)
        if response.status_code != 200:
            return None
        return response.json().get("entities", {}).get(id)

    def get_by_binomial(self, name: str) -> dict | None:
        """Fetches the Wikidata entity for a given taxon name"""

        headers = {"Accept": "application/sparql-results+json"}
        query = f"""
        SELECT ?item WHERE {{
          ?item wdt:{KnownWikiProperties.TAXON_NAME} "{name}".
        }}
        """
        print(f"looking up {name}")

        response = requests.get(self.SPARQL_ENDPOINT, headers=headers, params={"query": query})
        if response.status_code != 200:
            return None

        data = response.json()
        bindings = data.get("results", {}).get("bindings", [])
        if not bindings:
            return None

        qid = bindings[0]["item"]["value"].split("/")[-1]
        return self.get_by_id(qid)


@dataclass
class WikidataModel:
    name: str | None
    qid: str
    description: str | None
    claims: dict

    @classmethod
    def find_alias(cls, data: dict | None) -> str | None:
        if not data or "aliases" not in data:
            return None

        if "en" in data["aliases"]:
            en_alias = data["aliases"]["en"]
            return en_alias[0]["value"]

        return None

    @classmethod
    def find_description(cls, data: dict | None) -> str | None:
        if not data or "descriptions" not in data:
            return None

        if "en" in data["descriptions"]:
            return data["descriptions"]["en"]["value"]
        return None

    @classmethod
    def from_row(cls, row: list[Any]) -> "WikidataModel":
        (id, data) = row
        parsed = json.loads(data)

        alias = cls.find_alias(parsed)
        description = cls.find_description(parsed)

        return cls(qid=id, name=alias, description=description, claims={})


class WikidataMetadataReader:
    """Read
    * wikidata location information from cached geonames results
    * taxon information from Wikidata
    """

    def read(self, db: "SqliteDatabase") -> Iterator[SemanticTriple]:
        yield None
