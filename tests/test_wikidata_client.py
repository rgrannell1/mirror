"""Tests for the Wikidata HTTP client."""

from mirror.data import wikidata as wikidata_module
from mirror.data.wikidata import WikidataClient, WikidataModel


class FakeResponse:
    status_code = 200

    @staticmethod
    def json() -> dict:
        return {"entities": {"Q1": {"labels": {}}}}


class FakeSparqlResponse:
    status_code = 200

    @staticmethod
    def json() -> dict:
        bindings = [
            {"item": {"value": "http://www.wikidata.org/entity/L1369565-S1"}},
            {"item": {"value": "http://www.wikidata.org/entity/Q26972265"}},
        ]
        return {"results": {"bindings": bindings}}


def test_binomial_lookup_skips_lexemes(monkeypatch) -> None:
    """Proves taxon lookup returns the first Q-item, not a Latin lexeme sense."""
    monkeypatch.setattr(wikidata_module.requests, "get", lambda url, **kwargs: FakeSparqlResponse())

    assert WikidataClient().find_qid_by_binomial("Canis familiaris") == "Q26972265"


def test_find_taxon_name() -> None:
    """Proves the scientific taxon name (P225) is found, else None."""
    entity = WikidataModel(
        qid="Q9458574",
        data={
            "labels": {"en": {"value": "passerines"}},
            "claims": {"P225": [{"mainsnak": {"datavalue": {"value": "Passeriformes"}}}]},
        },
    )

    assert entity.find_taxon_name() == "Passeriformes"
    assert WikidataModel(qid="Q1", data={"labels": {}}).find_taxon_name() is None


def test_find_common_name() -> None:
    """Proves the English taxon common name (P1843) is found, else None."""
    entity = WikidataModel(
        qid="Q25365",
        data={
            "labels": {"en": {"value": "Gruidae"}},
            "claims": {
                "P1843": [
                    {"mainsnak": {"datavalue": {"value": {"text": "grue", "language": "fr"}}}},
                    {"mainsnak": {"datavalue": {"value": {"text": "cranes", "language": "en"}}}},
                ]
            },
        },
    )

    assert entity.find_common_name() == "cranes"
    assert WikidataModel(qid="Q1", data={"labels": {}}).find_common_name() is None


def test_find_label_falls_back_to_mul() -> None:
    """Proves entities labelled only under 'mul' (all languages) still give a label."""
    mul_only = WikidataModel(qid="Q25557", data={"labels": {"mul": {"value": "Gruiformes"}}})
    both = WikidataModel(
        qid="Q1",
        data={"labels": {"en": {"value": "bird"}, "mul": {"value": "Aves"}}},
    )

    assert mul_only.find_label() == "Gruiformes"
    assert both.find_label() == "bird"


def test_entity_requests_include_mul_language(monkeypatch) -> None:
    """Proves entity fetches request mul labels, which many taxa rely on."""
    captured = {}

    def fake_get(url, **kwargs):
        captured["url"] = url
        return FakeResponse()

    monkeypatch.setattr(wikidata_module.requests, "get", fake_get)
    WikidataClient().get_by_id("Q1")

    assert "languages=en%7Cmul" in captured["url"] or "languages=en|mul" in captured["url"]


def test_requests_carry_a_user_agent(monkeypatch) -> None:
    """Proves every Wikidata request sends a User-Agent; Wikimedia 403s without one."""
    captured = {}

    def fake_get(url, **kwargs):
        captured.update(kwargs)
        return FakeResponse()

    monkeypatch.setattr(wikidata_module.requests, "get", fake_get)
    WikidataClient().get_by_id("Q1")

    headers = captured.get("headers") or {}
    assert "User-Agent" in headers
    assert headers["User-Agent"].strip()
