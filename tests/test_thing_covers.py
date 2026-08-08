"""Tests for box-aware thing cover selection."""

from mirror.data.semantic_triples.photos import (
    CoverCandidate,
    candidate_fill,
    count_subjects,
    cover_sort_key,
    eligible_candidates,
    make_candidate,
    person_free,
)


def make(fpath: str, **overrides) -> CoverCandidate:
    """Build a candidate with neutral defaults."""
    fields = {
        "is_explicit": 0,
        "rating_rank": 0,
        "wild_rank": 1,
        "single_subject": 0,
        "has_person": 0,
        "fill": None,
    }
    fields.update(overrides)
    return CoverCandidate(fpath=fpath, **fields)


RANKING_CASES = [
    (
        "explicit assignment beats a higher-rated photo",
        [make("a", rating_rank=5), make("b", is_explicit=1, rating_rank=1)],
        "b",
    ),
    (
        "rating beats a bigger subject fill",
        [make("a", rating_rank=4, fill=0.1), make("b", rating_rank=3, fill=0.9)],
        "a",
    ),
    (
        "single-subject labelling wins within a rating band",
        [make("a", rating_rank=3, fill=0.9), make("b", rating_rank=3, single_subject=1)],
        "b",
    ),
    (
        "wild beats captive within a rating band",
        [make("a", rating_rank=3, wild_rank=0, fill=0.9), make("b", rating_rank=3, wild_rank=2)],
        "b",
    ),
    (
        "wild context outranks single-subject labelling",
        [
            make("a", rating_rank=3, wild_rank=0, single_subject=1),
            make("b", rating_rank=3, wild_rank=2),
        ],
        "b",
    ),
    (
        "fill breaks a full tie",
        [make("a", rating_rank=3, fill=0.2), make("b", rating_rank=3, fill=0.6)],
        "b",
    ),
    (
        "boxless photos rank neutrally, below any filled photo at equal rating",
        [make("a", rating_rank=3), make("b", rating_rank=3, fill=0.3)],
        "b",
    ),
]


def test_cover_ranking() -> None:
    """Proves cover order is explicit, then rating, then single-subject, then fill."""
    for label, candidates, expected in RANKING_CASES:
        best = max(eligible_candidates(candidates), key=cover_sort_key)
        assert best.fpath == expected, label


ELIGIBILITY_CASES = [
    (
        "tiny subjects are not eligible",
        [make("a", rating_rank=5, fill=0.01), make("b", rating_rank=1, fill=0.2)],
        "b",
    ),
    (
        "photos without box information stay eligible",
        [make("a", rating_rank=2), make("b", rating_rank=1, fill=0.2)],
        "a",
    ),
    (
        "a thing keeps a cover even when every subject is tiny",
        [make("a", rating_rank=2, fill=0.01), make("b", rating_rank=1, fill=0.02)],
        "a",
    ),
]


def test_cover_eligibility() -> None:
    """Proves the too-small rule excludes photos without ever leaving a thing coverless."""
    for label, candidates, expected in ELIGIBILITY_CASES:
        best = max(eligible_candidates(candidates), key=cover_sort_key)
        assert best.fpath == expected, label


PERSON_CASES = [
    (
        "a person photo is dropped no matter its rating",
        [make("a", rating_rank=5, has_person=1), make("b", rating_rank=1)],
        ["b"],
    ),
    (
        "an explicit assignment overrides the person rule",
        [make("a", is_explicit=1, has_person=1), make("b")],
        ["a", "b"],
    ),
    (
        "a subject with only person photos gets no cover",
        [make("a", has_person=1), make("b", has_person=1)],
        [],
    ),
]


def test_person_free() -> None:
    """Proves person photos are never covers, with no fallback, unless explicit."""
    for label, candidates, expected in PERSON_CASES:
        kept = [candidate.fpath for candidate in person_free(candidates)]
        assert kept == expected, label


def test_candidate_fill() -> None:
    """Proves fill needs both a box volume and an image area."""
    assert candidate_fill(None, 1000) is None
    assert candidate_fill(500, None) is None
    assert candidate_fill(500, 0) is None
    assert candidate_fill(500, 1000) == 0.5


def test_count_subjects() -> None:
    """Proves the summary subjects cell counts URNs, empty meaning none."""
    assert count_subjects("") == 0
    assert count_subjects("urn:ró:bird:a") == 1
    assert count_subjects("urn:ró:bird:a, urn:ró:mammal:b") == 2


def test_make_candidate_computes_subject_fill() -> None:
    """Proves subject rows use the scan's recorded area and labelling count."""
    owl_urn = "urn:ró:bird:tyto-alba"
    scans = {("p1", "bird"): (500, 1000)}
    row = ("/photo.jpg", "p1", owl_urn, "⭐⭐⭐", owl_urn, "subject")

    thing_urn, candidate = make_candidate(row, scans, {})

    assert thing_urn == "urn:ró:bird:tyto-alba"
    assert candidate.fill == 0.5
    assert candidate.single_subject == 1
    assert candidate.is_explicit == 0


def test_make_candidate_collapses_context_variants() -> None:
    """Proves context variants group under the base URN and rank by wildness."""
    gannet = "urn:ró:bird:morus-bassanus"
    scans = {("p1", "bird"): (500, 1000)}

    wild_row = ("/a.jpg", "p1", f"{gannet}?context=wild", "⭐", gannet, "subject")
    captive_row = ("/b.jpg", "p1", f"{gannet}?context=captivity", "⭐", gannet, "subject")
    plain_row = ("/c.jpg", "p1", gannet, "⭐", gannet, "subject")

    wild = make_candidate(wild_row, scans, {})
    captive = make_candidate(captive_row, scans, {})
    plain = make_candidate(plain_row, scans, {})

    assert wild[0] == captive[0] == plain[0] == gannet
    assert wild[1].wild_rank == 2
    assert plain[1].wild_rank == 1
    assert captive[1].wild_rank == 0
    # the context variant still finds its detection row via the base type
    assert wild[1].fill == 0.5


def test_make_candidate_area_fallbacks() -> None:
    """Proves legacy rows fall back to exif area, and empty scans rank neutrally."""
    owl_urn = "urn:ró:bird:tyto-alba"
    row = ("/photo.jpg", "p1", owl_urn, "⭐", owl_urn, "subject")

    legacy = make_candidate(row, {("p1", "bird"): (500, 0)}, {"/photo.jpg": 2000})[1]
    assert legacy.fill == 0.25

    empty_scan = make_candidate(row, {("p1", "bird"): (0, 1000)}, {})[1]
    assert empty_scan.fill is None

    unscanned = make_candidate(row, {}, {"/photo.jpg": 2000})[1]
    assert unscanned.fill is None


def test_make_candidate_explicit_cover() -> None:
    """Proves explicit cover rows are flagged and skip fill computation."""
    row = ("/photo.jpg", "p1", "urn:ró:bird:tyto-alba", "⭐", "", "cover")

    candidate = make_candidate(row, {}, {})[1]

    assert candidate.is_explicit == 1
    assert candidate.fill is None
