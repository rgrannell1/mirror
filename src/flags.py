"""Convert country names to flags"""

from typing import List


class Flags:
    TABLE = {
        "Ireland": "🇮🇪",
        "Germany": "🇩🇪",
        "United States of America": "🇺🇸",
        "England": "🏴󠁧󠁢󠁥󠁮󠁧󠁿",
        "Mallorca": "🇪🇸",
        "The Netherlands": "🇳🇱",
        "Northern Ireland": "🇬🇧",
        "Scotland": "🏴󠁧󠁢󠁳󠁣󠁴󠁿",
        "Lanzarote": "🇪🇸",
        "Switzerland": "🇨🇭",
        "France": "🇫🇷",
        "Spain": "🇪🇸",
        "Tenerife": "🇪🇸",
        "Norway": "🇳🇴",
        "Sweden": "🇸🇪",
        "Italy": "🇮🇹",
        "Wales": "🏴󠁧󠁢󠁷󠁬󠁳󠁿",
        "Slovenia": "🇸🇮",
    }

    @classmethod
    def from_country(cls, name: str) -> str:
        if name in Flags.TABLE:
            return Flags.TABLE[name]

        raise ValueError(f"Country {name} not found in flags table")

    @classmethod
    def from_countries(cls, countries: List[str]) -> str:
        return " ".join([Flags.from_country(country.strip()) for country in countries])
