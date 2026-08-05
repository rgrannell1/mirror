"""Tests for the selective per-role encoding filters.

Some renditions (social_card, banner) are only generated for a subset of source
files rather than every photo. These guard that scoping.
"""

from mirror.data.things import banner_fpaths
from mirror.workflows.upload.selective import is_role_skipped


def test_banner_role_only_generated_for_banner_sources():
    for fpath in banner_fpaths():
        assert not is_role_skipped("banner", fpath)
    assert is_role_skipped("banner", "/home/rg/Drive/Media/2022/Cranes/Published/not-a-banner.JPG")


def test_social_card_role_only_generated_for_cover_sources():
    assert not is_role_skipped("social_card", "/x/PkhvUKujrGo4+cover.jpg")
    assert is_role_skipped("social_card", "/x/regular.jpg")


def test_general_roles_never_skipped():
    # renditions without a selector are generated for every photo
    assert not is_role_skipped("mid_image_lossy", "/x/any.jpg")
    assert not is_role_skipped("thumbnail_lossy", "/x/any.jpg")
