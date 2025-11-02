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


FEATURES = {
    "urn:ró:place_feature:castle": "Castle",
    "urn:ró:place_feature:city": "City",
    "urn:ró:place_feature:harbor": "Harbour",
    "urn:ró:place_feature:national-park": "National Park",
    "urn:ró:place_feature:nature reserve": "Nature Reserve",
    "urn:ró:place_feature:port": "Port",
    "urn:ró:place_feature:rainforest": "Rainforest",
    "urn:ró:place_feature:unesco": "UNESCO",
    "urn:ró:place_feature:volcano": "Volcano",
    "urn:ró:place_feature:aquarium": "Aquarium",
    "urn:ró:place_feature:archaeological site": "Archaeological Site",
    "urn:ró:place_feature:beach": "Beach",
    "urn:ró:place_feature:bridge": "Bridge",
    "urn:ró:place_feature:canal": "Canal",
    "urn:ró:place_feature:castle": "Castle",
    "urn:ró:place_feature:cathedral": "Cathedral",
    "urn:ró:place_feature:cave": "Cave",
    "urn:ró:place_feature:city": "City",
    "urn:ró:place_feature:cliffs": "Cliffs",
    "urn:ró:place_feature:county": "County",
    "urn:ró:place_feature:district": "District",
    "urn:ró:place_feature:garden": "Garden",
    "urn:ró:place_feature:island": "Island",
    "urn:ró:place_feature:lake": "Lake",
    "urn:ró:place_feature:monastery": "Monastery",
    "urn:ró:place_feature:monument": "Monument",
    "urn:ró:place_feature:mosque": "Mosque",
    "urn:ró:place_feature:mountain": "Mountain",
    "urn:ró:place_feature:museum": "Museum",
    "urn:ró:place_feature:national-park": "National Park",
    "urn:ró:place_feature:nature reserve": "Nature Reserve",
    "urn:ró:place_feature:palace": "Palace",
    "urn:ró:place_feature:park": "Park",
    "urn:ró:place_feature:port": "Port",
    "urn:ró:place_feature:square": "Square",
    "urn:ró:place_feature:state": "State",
    "urn:ró:place_feature:street": "Street",
    "urn:ró:place_feature:town": "Town",
    "urn:ró:place_feature:train station": "Train Station",
    "urn:ró:place_feature:unesco": "UNESCO",
    "urn:ró:place_feature:village": "Village",
    "urn:ró:place_feature:volcano": "Volcano",
    "urn:ró:place_feature:waterfall": "Waterfall",
    "urn:ró:place_feature:wildlife-conservation": "Wildlife Conservation",
    "urn:ró:place_feature:zoo": "Zoo",
}

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

        for feature_urn, feature_name in FEATURES.items():
            yield SemanticTriple(
                source=feature_urn,
                relation=KnownRelations.NAME,
                target=feature_name,
            )

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
