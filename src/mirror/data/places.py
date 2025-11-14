"""Read place information from places.toml file and convert to semantic triples. This
information describes locations (but not actually the points that lie within it)
"""
import tomllib
from dataclasses import dataclass, field
from typing import Any, Dict, Iterator, List, Optional
from pathlib import Path

from mirror.constants import URN_PREFIX, KnownRelations
from mirror.data.types import SemanticTriple


@dataclass
class PlaceModel:
    """Place model from places.toml"""

    id: str
    name: str
    short_name: Optional[str] = None
    wikipedia: Optional[str] = None
    unesco_id: Optional[str] = None
    features: List[str] = field(default_factory=list)
    in_places: List[str] = field(default_factory=list)
    near_places: List[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PlaceModel":
        return cls(
            id=data["id"],
            name=data["name"],
            short_name=data.get("short_name"),
            wikipedia=data.get("wikipedia"),
            unesco_id=data.get("unesco_id"),
            features=data.get("features", []),
            in_places=data.get("in", []),
            near_places=data.get("near", []),
        )

class PlacesMetadataReader:
    """Read place information from places.toml file"""

    def __init__(self, places_file: str = "places.toml"):
        self.places_file = places_file

    def read(self, db) -> Iterator[SemanticTriple]:
        """Read places from TOML file and yield semantic triples"""
        places_path = Path(self.places_file)

        if not places_path.exists():
            return

        with open(places_path, 'rb') as f:
            data = tomllib.load(f)

        places = data.get("places", [])
        for place_data in places:
            model = PlaceModel.from_dict(place_data)
            yield from self.to_relations(model)

    def to_relations(self, model: PlaceModel) -> Iterator[SemanticTriple]:
        """Convert a PlaceModel to semantic triples"""

        yield SemanticTriple(
            source=model.id,
            relation=KnownRelations.NAME,
            target=model.name,
        )

        if model.short_name:
            yield SemanticTriple(
                source=model.id,
                relation=KnownRelations.SHORT_NAME,
                target=model.short_name,
            )

        if model.wikipedia:
            yield SemanticTriple(
                source=model.id,
                relation=KnownRelations.WIKIPEDIA,
                target=model.wikipedia,
            )

        if model.unesco_id:
            yield SemanticTriple(
                source=model.id,
                relation=KnownRelations.UNESCO_ID,
                target=model.unesco_id,
            )

        # Features
        for feature in model.features:
            yield SemanticTriple(
                source=model.id,
                relation=KnownRelations.FEATURE,
                target=feature,
            )

        # Location relationships (contained in)
        for in_place in model.in_places:
            yield SemanticTriple(
                source=model.id,
                relation=KnownRelations.IN,
                target=in_place,
            )

        for near_place in model.near_places:
            yield SemanticTriple(
                source=model.id,
                relation=KnownRelations.NEAR,
                target=near_place,
            )
