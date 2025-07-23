
import json
import requests
import xmltodict
from dataclasses import dataclass
from typing import Any, Dict, List, Union


class Geoname:
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
    alternate_names: str | None
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
            toponym_name=parsed.get("toponymName"),
            name=parsed.get("name"),
            lat=float(parsed["lat"]) if parsed.get("lat") is not None else None,
            lng=float(parsed["lng"]) if parsed.get("lng") is not None else None,
            geoname_id=int(parsed["geonameId"]),
            country_code=parsed.get("countryCode"),
            country_name=parsed.get("countryName"),
            fcl=parsed.get("fcl"),
            fcode=parsed.get("fcode"),
            fcl_name=parsed.get("fclName"),
            fcode_name=parsed.get("fcodeName"),
            population=int(parsed["population"]) if parsed.get("population") is not None else None,
            admin_code1=parsed.get("adminCode1"),
            admin_name1=parsed.get("adminName1"),
            ascii_name=parsed.get("asciiName"),
            alternate_names=parsed.get("alternateNames"),
            elevation=int(parsed["elevation"]) if parsed.get("elevation") is not None else None,
            srtm3=int(parsed["srtm3"]) if parsed.get("srtm3") is not None else None,
            astergdem=int(parsed["astergdem"]) if parsed.get("astergdem") is not None else None,
            continent_code=parsed.get("continentCode"),
            admin_code2=parsed.get("adminCode2"),
            admin_name2=parsed.get("adminName2"),
            timezone=parsed.get("timezone"),
        )
