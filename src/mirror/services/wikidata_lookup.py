"""Map Wikidata request failures to a service error."""

import requests

from mirror.data.wikidata import WikidataClient


class WikidataLookupError(Exception):
    """A Wikidata request failed."""


def fetch_entity_data(qid: str) -> dict | None:
    """Fetch one Wikidata entity."""
    return WikidataClient().get_by_id(qid)


def find_binomial_qid(binomial: str) -> str | None:
    """Find one binomial QID and hide the HTTP client exception."""
    try:
        return WikidataClient().find_qid_by_binomial(binomial)
    except requests.RequestException as err:
        raise WikidataLookupError(str(err)) from err
