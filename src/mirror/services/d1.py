"""Build the D1 SQLite snapshot used for social-card metadata."""

import os
from typing import NamedTuple

from mirror.commons.config import D1_DATABASE_PATH
from mirror.data.covers import (
    CoverSelection,
    cached_cover_selection,
    person_photo_fpaths,
    thing_card_pairs,
)
from mirror.data.things import thing_names, trip_titles, trip_to_albums
from mirror.services.database import D1SqliteDatabase, SqliteDatabase

# star rating of each album's cover photo, keyed by album dpath
COVER_RATING_QUERY = """
select photos.dpath, photo_metadata_table.target
from photos
join phashes on phashes.fpath = photos.fpath
join photo_metadata_table
  on photo_metadata_table.phash = phashes.phash
  and photo_metadata_table.relation = 'rating'
where photos.fpath like '%+cover%'
"""


def map_album_details(albums) -> dict:
    """Collect per-album social-card fields, keyed by dpath."""
    dpath_to_details: dict = {}

    for album in albums:
        details = dpath_to_details.setdefault(album.src, {})

        if album.relation == "summary":
            details["description"] = album.target

        if album.relation == "permalink":
            details["path"] = f"/album/{album.target}"
            details["permalink"] = album.target

        if album.relation == "title":
            details["title"] = album.target

    return dpath_to_details


def attach_cover_urls(dpath_to_details: dict, album_covers) -> None:
    """Attach each album's social-card image url."""
    for album_cover in album_covers:
        dpath = os.path.dirname(album_cover.fpath)

        if dpath_to_details.get(dpath):
            dpath_to_details[dpath]["image_url"] = album_cover.url


def map_permalink_to_dpath(dpath_to_details: dict) -> dict:
    """Map album permalink → dpath."""
    return {
        details["permalink"]: dpath
        for dpath, details in dpath_to_details.items()
        if "permalink" in details
    }


def collect_album_covers(dpath_to_details: dict, cover_ratings: dict, max_dates: dict) -> dict:
    """Map album dpath → (rating, max_date, image_url) for albums with a cover."""
    return {
        dpath: (cover_ratings.get(dpath, 0), max_dates.get(dpath, ""), details["image_url"])
        for dpath, details in dpath_to_details.items()
        if "image_url" in details
    }


def choose_trip_image(album_urns, permalink_to_dpath: dict, album_covers: dict) -> str | None:
    """Pick the trip card image: the highest-rated album cover, ties favouring
    the newest album."""
    best_cover = None

    for album_urn in album_urns:
        permalink = album_urn.rsplit(":", 1)[-1]
        dpath = permalink_to_dpath.get(permalink)

        cover = album_covers.get(dpath)
        if cover is None:
            continue

        if best_cover is None or cover > best_cover:
            best_cover = cover

    if best_cover is None:
        return None
    return best_cover[2]


def add_album_cards(socials, dpath_to_details: dict) -> list[str]:
    """Add one social-card row per album. Returns the paths of albums skipped
    because no usable card image exists."""
    skipped: list[str] = []

    for details in dpath_to_details.values():
        if "image_url" not in details:
            skipped.append(details["path"])
            continue

        socials.add(
            path=details["path"],
            description=details["description"],
            title=details["title"],
            image_url=details["image_url"],
        )
    return skipped


class ThingCard(NamedTuple):
    """One thing page's social-card row."""

    path: str
    title: str
    image_url: str


def thing_display_name(thing_urn: str, names: dict[str, str]) -> str:
    """The thing's curated name, else its title-cased URN id."""
    if thing_urn in names:
        return names[thing_urn]

    thing_id = thing_urn.rsplit(":", 1)[-1]
    return thing_id.replace("-", " ").title()


def thing_path(thing_urn: str) -> str:
    """The thing page path for a URN: urn:ró:bird:robin → /thing/bird:robin."""
    return f"/thing/{thing_urn.removeprefix('urn:ró:')}"


def thing_card_rows(
    selection: CoverSelection, social_urls: dict, mid_urls: dict, names: dict[str, str]
) -> tuple[list[ThingCard], list[str]]:
    """Build thing card rows. Also returns the things whose cover lacked a
    social_card encode and fell back to the mid-size image."""
    cards: list[ThingCard] = []
    fallbacks: list[str] = []

    for thing_urn, fpath in thing_card_pairs(selection):
        image_url = social_urls.get(fpath)
        if image_url is None:
            image_url = mid_urls.get(fpath)
            if image_url is None:
                continue
            fallbacks.append(thing_urn)

        title = thing_display_name(thing_urn, names)
        cards.append(ThingCard(path=thing_path(thing_urn), title=title, image_url=image_url))

    return cards, fallbacks


class D1Builder:
    """Populate the D1 cache DB from the main media index for social cards."""

    def __init__(self, db: SqliteDatabase) -> None:
        self.db = db

    def read_cover_ratings(self) -> dict:
        """Map album dpath → cover photo star count."""
        return {dpath: len(stars) for dpath, stars in self.db.conn.execute(COVER_RATING_QUERY)}

    def read_max_dates(self) -> dict:
        """Map album dpath → newest photo date."""
        return {album.dpath: album.max_date or "" for album in self.db.album_data_view().list()}

    def add_trip_cards(self, socials, dpath_to_details: dict) -> None:
        """Add one social-card row per titled trip."""
        permalink_to_dpath = map_permalink_to_dpath(dpath_to_details)
        album_covers = collect_album_covers(
            dpath_to_details, self.read_cover_ratings(), self.read_max_dates()
        )
        titles = trip_titles()

        for trip_urn, album_urns in trip_to_albums().items():
            image_url = choose_trip_image(album_urns, permalink_to_dpath, album_covers)
            title = titles.get(trip_urn)
            if image_url is None or title is None:
                continue

            trip_number = trip_urn.rsplit(":", 1)[-1]
            socials.add(
                path=f"/trip/{trip_number}",
                description=None,
                title=title,
                image_url=image_url,
            )

    def urls_by_role(self, role: str) -> dict[str, str]:
        """Map fpath → encoded image url for one rendition role.

        Photos with a person subject are excluded: they never become cards.
        """
        blocked = person_photo_fpaths(self.db)
        return {
            enc.fpath: enc.url
            for enc in self.db.encoded_photos_table().list_by_role(role)
            if enc.fpath not in blocked
        }

    def add_thing_cards(self, socials) -> list[str]:
        """Add one social-card row per thing with a cover. Returns the things
        whose cover lacked a social_card encode and fell back to mid-size."""
        selection = cached_cover_selection(self.db)
        cards, fallbacks = thing_card_rows(
            selection,
            self.urls_by_role("social_card"),
            self.urls_by_role("mid_image_lossy"),
            thing_names(),
        )

        for card in cards:
            socials.add(
                path=card.path, description=None, title=card.title, image_url=card.image_url
            )
        return fallbacks

    def build(self) -> dict:
        """Build and dump every social card. Returns a card-quality summary."""
        d1 = D1SqliteDatabase(D1_DATABASE_PATH)

        dpath_to_details = map_album_details(self.db.media_metadata_table().list_albums())

        blocked = person_photo_fpaths(self.db)
        album_covers = [
            enc
            for enc in self.db.encoded_photos_table().list_by_role("social_card")
            if enc.fpath not in blocked
        ]
        attach_cover_urls(dpath_to_details, album_covers)

        socials = d1.social_card_table()
        skipped_albums = add_album_cards(socials, dpath_to_details)
        self.add_trip_cards(socials, dpath_to_details)
        fallbacks = self.add_thing_cards(socials)

        d1.dump()
        return {"thing_fallbacks": fallbacks, "skipped_albums": skipped_albums}
