from typing import Iterator
from mirror.data.types import SemanticTriple

flags = {
  "urn:ró:country:england": "🏴󠁧󠁢󠁥󠁮󠁧󠁿",
  "urn:ró:country:france": "🇫🇷",
  "urn:ró:country:germany": "🇩🇪",
  "urn:ró:country:ireland": "🇮🇪",
  "urn:ró:country:italy": "🇮🇹",
  "urn:ró:country:lanzarote": "🇪🇸",
  "urn:ró:country:mallorca": "🇪🇸",
  "urn:ró:country:northern-ireland": "🇬🇧",
  "urn:ró:country:norway": "🇳🇴",
  "urn:ró:country:scotland": "🏴󠁧󠁢󠁳󠁣󠁴󠁿",
  "urn:ró:country:slovenia": "🇸🇮",
  "urn:ró:country:spain": "🇪🇸",
  "urn:ró:country:sweden": "🇸🇪",
  "urn:ró:country:switzerland": "🇨🇭",
  "urn:ró:country:tenerife": "🇪🇸",
  "urn:ró:country:the-netherlands": "🇳🇱",
  "urn:ró:country:united-states-of-america": "🇺🇸",
  "urn:ró:country:wales": "🏴󠁧󠁢󠁷󠁬󠁳󠁿",
  }

class CountriesReader:
    def read(self, db: "SqliteDatabase") -> Iterator[SemanticTriple]:
        albums = list(db.album_data_view().list())

        seen_countries: set[str] = set()

        for album in albums:
            for country in album.flags:
                if country not in seen_countries:
                    seen_countries.add(country)

                    country_id = country.lower().replace(' ', '-')
                    urn = f"urn:ró:country:{country_id}"

                    yield SemanticTriple(urn, "name", country)
                    yield SemanticTriple(urn, "flag", flags.get(urn, "🏴"))
