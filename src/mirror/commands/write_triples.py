import re
from urllib.parse import parse_qs, urlparse
from typing import Optional, Dict, Any

try:
    from neo4j import GraphDatabase

    NEO4J_AVAILABLE = True
except ImportError:
    GraphDatabase = None  # type: ignore
    NEO4J_AVAILABLE = False
    print("Warning: neo4j package not installed. Run: pip install neo4j")

from mirror.commands.publisher import TriplesArtifact


def parse_urn(urn: str) -> Optional[Dict[str, Any]]:
    """Parse a URN in the format urn:ró:<type>:<id>?<querystring>"""
    if not urn.startswith("urn:ró:"):
        return None

    # Remove the urn:ró: prefix
    remainder = urn[7:]

    # Split on the first two colons to get type and id+query
    parts = remainder.split(":", 2)
    if len(parts) < 2:
        return None

    urn_type = parts[0]
    id_and_query = parts[1]

    # Check if there's a query string
    if "?" in id_and_query:
        urn_id, query_string = id_and_query.split("?", 1)
        # Parse query parameters
        query_params = parse_qs(query_string)
        # Flatten single-value parameters
        properties = {k: v[0] if len(v) == 1 else v for k, v in query_params.items()}
    else:
        urn_id = id_and_query
        properties = {}

    return {"type": urn_type, "id": urn_id, "properties": properties}


def is_urn(value: str) -> bool:
    """Check if a value is a URN starting with urn:ró:"""
    return isinstance(value, str) and value.startswith("::")


def create_node_query(parsed_urn: dict) -> tuple[str, dict]:
    """Create a Cypher query to merge a node with its properties"""
    node_type = parsed_urn["type"].capitalize()
    node_id = parsed_urn["id"]
    properties = parsed_urn["properties"]

    # Build property string for the query
    prop_assignments = []
    params = {"id": node_id}

    for key, value in properties.items():
        param_name = f"prop_{key}"
        prop_assignments.append(f"n.{key} = ${param_name}")
        params[param_name] = value

    prop_clause = f"SET {', '.join(prop_assignments)}" if prop_assignments else ""

    query = f"""
    MERGE (n:{node_type} {{id: $id}})
    {prop_clause}
    RETURN n
    """

    return query.strip(), params


def create_relationship_query(source_parsed: dict, relation: str, target_parsed: dict) -> tuple[str, dict]:
    """Create a Cypher query to merge a relationship between two nodes"""
    source_type = source_parsed["type"].capitalize()
    target_type = target_parsed["type"].capitalize()

    # Sanitize relation name for Cypher (remove special characters, spaces, etc.)
    safe_relation = re.sub(r"[^a-zA-Z0-9_]", "_", relation).upper()

    params = {"source_id": source_parsed["id"], "target_id": target_parsed["id"]}

    # Add source properties
    source_props = []
    for key, value in source_parsed["properties"].items():
        param_name = f"source_{key}"
        source_props.append(f"s.{key} = ${param_name}")
        params[param_name] = value

    # Add target properties
    target_props = []
    for key, value in target_parsed["properties"].items():
        param_name = f"target_{key}"
        target_props.append(f"t.{key} = ${param_name}")
        params[param_name] = value

    source_prop_clause = f"SET {', '.join(source_props)}" if source_props else ""
    target_prop_clause = f"SET {', '.join(target_props)}" if target_props else ""

    query = f"""
    MERGE (s:{source_type} {{id: $source_id}})
    {source_prop_clause}
    MERGE (t:{target_type} {{id: $target_id}})
    {target_prop_clause}
    MERGE (s)-[r:{safe_relation}]->(t)
    RETURN s, r, t
    """

    return query.strip(), params


def create_property_query(source_parsed: dict, relation: str, target_value: str) -> tuple[str, dict]:
    """Create a Cypher query to set a property on a node"""
    node_type = source_parsed["type"].capitalize()

    # Sanitize property name
    safe_property = re.sub(r"[^a-zA-Z0-9_]", "_", relation)

    params = {"id": source_parsed["id"], "property_value": target_value}

    # Add existing properties
    prop_assignments = [f"n.{safe_property} = $property_value"]
    for key, value in source_parsed["properties"].items():
        param_name = f"prop_{key}"
        prop_assignments.append(f"n.{key} = ${param_name}")
        params[param_name] = value

    query = f"""
    MERGE (n:{node_type} {{id: $id}})
    SET {", ".join(prop_assignments)}
    RETURN n
    """

    return query.strip(), params


def write_neo4j_triples(db, neo4j_uri="bolt://localhost:7687", neo4j_user="neo4j", neo4j_password="password") -> None:
    """Write triples from the database to Neo4j"""

    if not NEO4J_AVAILABLE or GraphDatabase is None:
        print("Error: neo4j package is required. Install with: pip install neo4j")
        return

    # Connect to Neo4j
    driver = GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password))

    try:
        reader = TriplesArtifact()

        with driver.session() as session:
            for source, relation, target in reader.read(db):
                # Parse source
                source_parsed = parse_urn(source.replace("::", "urn:ró:")) if is_urn(source) else None
                target_parsed = parse_urn(target.replace("::", "urn:ró:")) if is_urn(target) else None

                # Handle different cases
                if source_parsed and target_parsed:
                    # Case 1: <urn> <relation> <urn> - create relationship between nodes
                    query, params = create_relationship_query(source_parsed, relation, target_parsed)
                    session.run(query, params)
                    print(
                        f"Created relationship: {source_parsed['type']}:{source_parsed['id']} -{relation}-> {target_parsed['type']}:{target_parsed['id']}"
                    )

                elif source_parsed and not target_parsed:
                    # Case 2: <urn> <relation> <string> - add property to node
                    query, params = create_property_query(source_parsed, relation, target)
                    session.run(query, params)
                    print(f"Set property: {source_parsed['type']}:{source_parsed['id']}.{relation} = '{target}'")

                else:
                    # Case 3: <string> <relation> <any> - warn and skip
                    print(f"WARNING: Skipping triple with string source: '{source}' -{relation}-> '{target}'")
                    continue

    finally:
        driver.close()
    ...
