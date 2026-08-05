"""Validate Mirror's processed triples with SHACL and return normal audit findings."""

from pathlib import Path

from pyshacl import validate
from rdflib import Graph
from rdflib.namespace import RDF, SH

from mirror.audit.audit_types import Finding
from mirror.audit.rdf_adapter import AUDIT, build_rdf_graph
from mirror.data.things import animal_types

SHAPES_PATH = Path(__file__).with_name("shapes.ttl")


def result_text(report: Graph, result, predicate) -> str:
    """Read a required text value from one SHACL validation result."""
    value = report.value(result, predicate)
    if value is None:
        raise ValueError(f"SHACL result has no {predicate}")
    return str(value)


def finding_from_result(data: Graph, report: Graph, result) -> Finding:
    """Convert one SHACL validation result into the existing audit finding type."""
    focus = report.value(result, SH.value) or report.value(result, SH.focusNode)
    if focus is None:
        raise ValueError("SHACL result has no focus node")
    subject = data.value(focus, AUDIT.originalValue)
    if subject is None:
        raise ValueError(f"SHACL focus node has no original value: {focus}")
    source_shape = result_text(report, result, SH.sourceShape)
    return Finding(
        check=source_shape.rsplit("/", 1)[-1],
        subject=str(subject),
        detail=result_text(report, result, SH.resultMessage),
    )


def load_shapes() -> Graph:
    """Parse the SHACL shapes, filling the animal-types token from things.toml."""
    shapes_text = SHAPES_PATH.read_text()
    shapes_text = shapes_text.replace("__ANIMAL_TYPES__", "|".join(animal_types()))
    return Graph().parse(data=shapes_text, format="turtle")


def validate_triples(triples: list[list]) -> list[Finding]:
    """Validate processed triples against Mirror's graph contract."""
    data = build_rdf_graph(triples)
    shapes = load_shapes()
    _, report, report_text = validate(data, shacl_graph=shapes)
    if not isinstance(report, Graph):
        raise ValueError(f"SHACL validation failed: {report_text}")
    results = report.subjects(RDF.type, SH.ValidationResult)
    findings = [finding_from_result(data, report, result) for result in results]
    return sorted(findings, key=lambda finding: (finding.check, finding.subject))
