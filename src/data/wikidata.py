import requests

class Wikidata:
    SPARQL_ENDPOINT = "https://query.wikidata.org/sparql"
    API_ENDPOINT = "https://www.wikidata.org/w/api.php"

    def get_by_id(self, id: str) -> dict | None:
        """Fetches full entity data from Wikidata by QID."""
        url = f"{self.API_ENDPOINT}?action=wbgetentities&ids={id}&format=json&languages=en"
        response = requests.get(url)
        if response.status_code != 200:
            return None
        return response.json().get("entities", {}).get(id)

    def get_by_taxon_name(self, name: str) -> dict | None:
        """Fetches the Wikidata entity for a given taxon name (P225)."""
        headers = {"Accept": "application/sparql-results+json"}
        query = f"""
        SELECT ?item WHERE {{
          ?item wdt:P225 "{name}".
        }}
        """

        response = requests.get(self.SPARQL_ENDPOINT, headers=headers, params={"query": query})
        if response.status_code != 200:
            return None

        data = response.json()
        bindings = data.get("results", {}).get("bindings", [])
        if not bindings:
            return None

        qid = bindings[0]["item"]["value"].split("/")[-1]
        return self.get_by_id(qid)
