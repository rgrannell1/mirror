"""Build an audit-only RDF graph from Mirror's published triple representation."""

from urllib.parse import quote

from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import RDF

AUDIT = Namespace("https://photos.rgrannell.xyz/audit/")
NODE_ROOT = f"{AUDIT}node/"
RELATION_ROOT = f"{AUDIT}relation/"


def canonicalise_resource(value: str) -> str:
    """Strip query context from a bracketed Mirror resource."""
    if not value.startswith("[") or not value.endswith("]"):
        return value
    body = value[1:-1].split("?", 1)[0]
    return f"[{body}]"


def display_resource(value: str) -> str:
    """Restore the public spelling used for a canonical Mirror resource."""
    canonical = canonicalise_resource(value)
    if not canonical.startswith("[i:"):
        return canonical
    return f"urn:ró:{canonical[3:-1]}"


def resource_uri(value: str) -> URIRef:
    """Map a Mirror resource to a safe, deterministic internal IRI."""
    canonical = canonicalise_resource(value)
    return URIRef(f"{NODE_ROOT}{quote(canonical, safe='')}")


def predicate_uri(relation: str) -> URIRef:
    """Map a Mirror relation to an internal predicate IRI."""
    return URIRef(f"{RELATION_ROOT}{quote(relation, safe='')}")


def is_resource(value: object) -> bool:
    """Return whether a published target uses Mirror's bracketed resource form."""
    return isinstance(value, str) and value.startswith("[") and value.endswith("]")


def add_resource_metadata(graph: Graph, node: URIRef, value: str) -> None:
    """Retain the public resource spelling for readable validation findings."""
    graph.add((node, AUDIT.originalValue, Literal(display_resource(value))))


def add_album_link(graph: Graph, subject: URIRef, album_id: str) -> None:
    """Add the audit-only resource link implied by a literal albumId."""
    album_value = f"[i:album:{album_id}]"
    album = resource_uri(album_value)
    add_resource_metadata(graph, album, album_value)
    graph.add((subject, AUDIT.album, album))


def add_processed_triple(graph: Graph, triple: list) -> None:
    """Add one processed publication triple and its audit-only metadata."""
    source, relation, target = triple
    subject = resource_uri(source)
    predicate = predicate_uri(relation)
    add_resource_metadata(graph, subject, source)
    graph.add((subject, AUDIT.isSource, Literal(True)))
    if relation == "albumId" and isinstance(target, str):
        add_album_link(graph, subject, target)
    if is_resource(target):
        target_node = resource_uri(target)
        add_resource_metadata(graph, target_node, target)
        graph.add((subject, predicate, target_node))
        return
    graph.add((subject, predicate, Literal(target)))


def build_rdf_graph(triples: list[list]) -> Graph:
    """Convert processed publication triples into an in-memory RDF graph."""
    graph = Graph()
    graph.add((AUDIT.graph, RDF.type, AUDIT.PublicationGraph))
    for triple in triples:
        add_processed_triple(graph, triple)
    return graph
