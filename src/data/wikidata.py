import requests

class Wikidata:
  def get_by_id(self, id: str) -> dict | None:
    """Fetches data from Wikidata by ID."""
    url = f"https://www.wikidata.org/w/api.php?action=wbgetentities&ids={id}&format=json&llanguage=en"
    response = requests.get(url)

    return response.json().get("entities", {}).get(id)
