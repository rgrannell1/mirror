"""Tests for publication audit rules."""

from mirror.audit.shacl import validate_triples


def make_valid_triples() -> list[list]:
    """Build one complete photo and its album."""
    return [
        ["[i:photo:one]", "subject", "[i:bird:named]"],
        ["[i:photo:one]", "albumId", "album-one"],
        ["[i:photo:one]", "createdAt", "1"],
        ["[i:photo:one]", "thumbnailUrl", "[photos:one-thumbnail]"],
        ["[i:photo:one]", "midImageLossyUrl", "[photos:one-mid]"],
        ["[i:photo:one]", "previewJpegUrl", "[photos:one-preview]"],
        ["[i:photo:one]", "pngUrl", "[photos:one-png]"],
        ["[i:photo:one]", "fullImage", "[photos:one-full]"],
        ["[i:photo:one]", "mosaicColours", "abcdef"],
        ["[i:photo:one]", "rating", "[i:rating:2]"],
        ["[i:photo:one]", "location", "[i:geoname:123]"],
        ["[i:bird:named]", "name", "Named bird"],
        ["[i:geoname:123]", "name", "Named location"],
        ["[i:album:album-one]", "name", "Album one"],
        ["[i:album:album-one]", "photosCount", "1"],
        ["[i:album:album-one]", "videosCount", "0"],
        ["[i:album:album-one]", "minDate", "1"],
        ["[i:album:album-one]", "maxDate", "1"],
        ["[i:album:album-one]", "dateRange", "Today"],
        ["[i:album:album-one]", "shortDateRange", "Today"],
        ["[i:album:album-one]", "thumbnailUrl", "[photos:album-thumbnail]"],
        ["[i:album:album-one]", "mosaic", "abcdef"],
        ["[i:album:album-one]", "description", "Description"],
    ]


def test_shacl_audit_reports_animal_without_name() -> None:
    """Proves SHACL audits processed triples without changing their representation."""
    triples = make_valid_triples()
    triples.extend([
        ["[i:observation:two]", "subject", "[i:insect:missing?context=wild]"],
        ["[i:observation:three]", "subject", "[i:car:not-an-animal]"],
    ])

    findings = validate_triples(triples)

    assert [(finding.check, finding.subject) for finding in findings] == [
        ("animal-missing-name", "urn:ró:insect:missing"),
        ("triple-graph-invalid", "urn:ró:observation:three"),
    ]


def test_shacl_audit_checks_photo_album_and_reference_structure() -> None:
    """Proves the graph contract checks required fields, values, dates, and album links."""
    triples = [
        triple
        for triple in make_valid_triples()
        if not (triple[0] == "[i:photo:one]" and triple[1] == "midImageLossyUrl")
    ]
    for triple in triples:
        if triple[:2] == ["[i:photo:one]", "rating"]:
            triple[2] = "[i:rating:8]"
        if triple[:2] == ["[i:photo:one]", "albumId"]:
            triple[2] = "missing-album"
        if triple[:2] == ["[i:album:album-one]", "maxDate"]:
            triple[2] = "0"

    details = {finding.detail for finding in validate_triples(triples)}

    assert details == {
        "album minDate must not exceed maxDate",
        "albumId does not resolve to a named album",
        "photo is missing required fields: midImageLossyUrl",
        "rating must be one of urn:ró:rating:0 through urn:ró:rating:4",
    }
