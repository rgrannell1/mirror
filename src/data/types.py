
from attr import dataclass


@dataclass
class SemanticTriple:
    source: str
    relation: str
    target: str
