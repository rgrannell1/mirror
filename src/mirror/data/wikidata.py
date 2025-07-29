import json
from typing import Any, Iterator
import Levenshtein
from attr import dataclass
import requests

from mirror.constants import URN_PREFIX, KnownRelations, KnownTypes, KnownWikiProperties
from mirror.data.binomials import binomial_to_urn
from mirror.data.types import SemanticTriple


def to_pascal_case(s):
    return " ".join(word.capitalize() for word in s.replace("_", " ").replace("-", " ").split())


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
    qid: str
    data: dict | None = None

    def find_label(self) -> str | None:
        data = self.data
        if not data:
            return None

        return data.get("labels", {}).get("en", {}).get("value")

    def find_description(self) -> str | None:
        data = self.data
        if not data or "descriptions" not in data:
            return None

        if "en" in data["descriptions"]:
            return data["descriptions"]["en"]["value"]
        return None

    def find_alias(self) -> str | None:
        data = self.data

        if not data or "aliases" not in data:
            return None

        aliases = data["aliases"].get("en", [])
        if not aliases:
            return None

        return aliases[0]["value"] if aliases else None

    def find_wikipedia_link(self) -> str | None:
        data = self.data
        if not data or "sitelinks" not in data:
            return None

        sitelinks = data["sitelinks"]
        if "enwiki" in sitelinks:
            title = sitelinks["enwiki"]["title"]
            return f"https://en.wikipedia.org/wiki/{title.replace(' ', '_')}"

        return None

    @classmethod
    def from_row(cls, row: list[Any]) -> "WikidataModel":
        (id, data) = row
        parsed = json.loads(data)

        return cls(qid=id, data=parsed)


class WikidataMetadataReader:
    """Read
    * wikidata location information from cached geonames results
    * taxon information from Wikidata
    """

    def binomial_to_common_name(self, binomial: str, label: str, alias: str) -> str:
        # neither label present; return the binomial
        if not label and not alias:
            return binomial

        # the label is not present, but the alias is. Use the alias
        if not label:
            return to_pascal_case(alias)

        # the label is present, but the alias is not. Use the label
        if not alias:
            return to_pascal_case(label)

        # both are present; compute Levenstein distances from the binomial
        # since one is likely to be the binomial, one the common name
        binomial_label_diff = Levenshtein.distance(binomial.lower(), label.lower())
        binomial_alias_diff = Levenshtein.distance(binomial.lower(), alias.lower())

        label_more_similar = binomial_label_diff < binomial_alias_diff
        if label_more_similar:
            return to_pascal_case(alias)

        return to_pascal_case(label)

    def read_binomial_common_names(self, db: "SqliteDatabase") -> Iterator[SemanticTriple]:
        binomials_table = db.binomials_wikidata_id_table()
        wikidata_table = db.wikidata_table()

        binomial_to_qid = {binomial: qid for binomial, qid in binomials_table.list() if qid}

        for binomial, qid in binomial_to_qid.items():
            if not wikidata_table.has(qid):
                continue

            wikidata_data = wikidata_table.get_by_id(qid)
            if not wikidata_data:
                continue

            label = wikidata_data.find_label()
            alias = wikidata_data.find_alias()

            common_name = self.binomial_to_common_name(binomial, label, alias)

            urn = binomial_to_urn(db, binomial)
            if not urn:
                continue

            yield SemanticTriple(
                source=urn,
                relation=KnownRelations.NAME,
                target=common_name,
            )

    def read_wikipedia_urls(self, db: "SqliteDatabase") -> Iterator[SemanticTriple]:
        wikidata_table = db.wikidata_table()

        qids_to_urls = {}

        for data in wikidata_table.list():
            url = data.find_wikipedia_link()
            if not url:
                continue

            qids_to_urls[data.qid] = url

        binomials_table = db.binomials_wikidata_id_table()
        for qid, url in qids_to_urls.items():
            binomial = binomials_table.get_binomial(qid)
            if not binomial:
                continue

            urn = binomial_to_urn(db, binomial)
            if not urn:
                continue

            yield SemanticTriple(
                source=urn,
                relation=KnownRelations.WIKIPEDIA,
                target=url,
            )

    def read(self, db: "SqliteDatabase") -> Iterator[SemanticTriple]:
        yield from self.read_binomial_common_names(db)
        yield from self.read_wikipedia_urls(db)
