
import requests
import xmltodict


class Geoname:
    def __init__(self, username: str):
        self.username = username

    def get_by_id(self, id: str) -> dict | None:
        res = requests.get(f"http://secure.geonames.org/get?geonameId={id}&username={self.username}")
        xpars = xmltodict.parse(res.text)

        return xpars["geoname"] if "geoname" in xpars else None
