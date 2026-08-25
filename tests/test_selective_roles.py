"""Tests for the selective per-role encoding filters.

Some renditions (social_card, banner) are only generated for a subset of source
files rather than every photo. These guard that scoping.
"""

from mirror.data.things import banner_fpaths
from mirror.services import selective_upload
from mirror.services.selective_upload import is_role_skipped


def test_banner_role_only_generated_for_banner_sources():
    for fpath in banner_fpaths():
        assert not is_role_skipped("banner", fpath)
    assert is_role_skipped("banner", "/home/rg/Drive/Media/2022/Cranes/Published/not-a-banner.JPG")


def test_social_card_role_only_generated_for_cover_sources(monkeypatch):
    """Proves social_card encodes are gated to album covers and computed thing covers."""
    computed = frozenset({"/x/thing-cover.jpg"})
    monkeypatch.setattr(selective_upload, "computed_cover_fpaths", lambda: computed)
    monkeypatch.setattr(selective_upload, "person_blocked_fpaths", frozenset)

    assert not is_role_skipped("social_card", "/x/PkhvUKujrGo4+cover.jpg")
    assert not is_role_skipped("social_card", "/x/thing-cover.jpg")
    assert is_role_skipped("social_card", "/x/regular.jpg")


def test_person_photos_never_get_social_cards(monkeypatch):
    """Proves a photo with a person subject never gets a social_card encode,
    even as an album cover or computed thing cover."""
    blocked = frozenset({"/x/friends+cover.jpg", "/x/thing-cover.jpg"})
    monkeypatch.setattr(selective_upload, "computed_cover_fpaths", lambda: blocked)
    monkeypatch.setattr(selective_upload, "person_blocked_fpaths", lambda: blocked)

    assert is_role_skipped("social_card", "/x/friends+cover.jpg")
    assert is_role_skipped("social_card", "/x/thing-cover.jpg")


def test_general_roles_never_skipped():
    # renditions without a selector are generated for every photo
    assert not is_role_skipped("mid_image_lossy", "/x/any.jpg")
    assert not is_role_skipped("thumbnail_lossy", "/x/any.jpg")
