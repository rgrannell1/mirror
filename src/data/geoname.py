import json
import requests
import xmltodict
from dataclasses import dataclass
from typing import Any, Dict, Iterator, List

from src.constants import URN_PREFIX, KnownRelations, KnownTypes
from src.data.types import SemanticTriple


class GeonameClient:
    def __init__(self, username: str):
        self.username = username

    def get_by_id(self, id: str) -> dict | None:
        res = requests.get(f"http://secure.geonames.org/get?geonameId={id}&username={self.username}")
        xpars = xmltodict.parse(res.text)

        return xpars["geoname"] if "geoname" in xpars else None


@dataclass
class GeonameModel:
    """Geoname database model"""

    toponym_name: str
    name: str
    lat: float | None
    lng: float | None
    geoname_id: int
    country_code: str
    country_name: str
    fcl: str
    fcode: str
    fcl_name: str
    fcode_name: str
    population: int | None
    admin_code1: Dict[str, str]
    admin_name1: str
    ascii_name: str
    alternate_name: list
    elevation: int | None
    srtm3: int | None
    astergdem: int | None
    continent_code: str
    admin_code2: Dict[str, str] | str
    admin_name2: str
    timezone: Dict[str, str]

    @classmethod
    def from_row(cls, row: List[Any]) -> "GeonameModel":
        (id, data) = row
        parsed = json.loads(data)

        return cls(
            toponym_name=parsed["toponymName"],
            name=parsed["name"],
            lat=float(parsed["lat"]) if parsed.get("lat") is not None else None,
            lng=float(parsed["lng"]) if parsed.get("lng") is not None else None,
            geoname_id=int(parsed["geonameId"]),
            country_code=parsed["countryCode"],
            country_name=parsed["countryName"],
            fcl=parsed["fcl"],
            fcode=parsed["fcode"],
            fcl_name=parsed["fclName"],
            fcode_name=parsed["fcodeName"],
            population=int(parsed["population"]) if parsed.get("population") is not None else None,
            admin_code1=parsed["adminCode1"],
            admin_name1=parsed["adminName1"],
            ascii_name=parsed["asciiName"],
            alternate_name=parsed.get("alternateName", []),
            elevation=int(parsed["elevation"]) if parsed.get("elevation") is not None else None,
            srtm3=int(parsed["srtm3"]) if parsed.get("srtm3") is not None else None,
            astergdem=int(parsed["astergdem"]) if parsed.get("astergdem") is not None else None,
            continent_code=parsed["continentCode"],
            admin_code2=parsed["adminCode2"],
            admin_name2=parsed["adminName2"],
            timezone=parsed["timezone"],
        )


class GeonameMetadataReader:
    """Read location information from cached geonames results"""

    def read(self, db: "SqliteDatabase") -> Iterator[SemanticTriple]:
        geoname_table = db.geoname_table()

        for model in geoname_table.list():
            yield from self.to_relations(model)

    def to_relations(self, model: GeonameModel) -> Iterator[SemanticTriple]:
        """Convert a GeonameModel to PhotoMetadataModel relations"""

        fields = [
            (KnownRelations.NAME, model.toponym_name),
            (KnownRelations.LATITUDE, str(model.lat)),
            (KnownRelations.LONGITUDE, str(model.lng)),
            (KnownRelations.COUNTRY, model.country_name),
            (KnownRelations.FCODE, model.fcode),
            (KnownRelations.FCODE_NAME, model.fcode_name),
        ]

        for relation, target in fields:
            yield SemanticTriple(
                source=f"{URN_PREFIX}:{KnownTypes.GEONAME}:{model.geoname_id}",
                relation=relation,
                target=target,
            )

        for alt in model.alternate_name:
            if isinstance(alt, str):
                continue

            lang = alt.get("@lang", "unknown")
            text = alt.get("#text", "")

            if lang == "link" and "wikipedia.org" in text:
                yield SemanticTriple(
                    source=f"{URN_PREFIX}:{KnownTypes.GEONAME}:{model.geoname_id}",
                    relation=KnownRelations.WIKIPEDIA,
                    target=text,
                )
            elif lang == "wkdt":
                yield SemanticTriple(
                    source=f"{URN_PREFIX}:{KnownTypes.GEONAME}:{model.geoname_id}",
                    relation=KnownRelations.WIKIDATA,
                    target=text,
                )
