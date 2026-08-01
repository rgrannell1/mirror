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
        ["[i:place:148]", "name", "Ireland"],
        ["[i:place:148]", "flag", "🇮🇪"],
        ["[i:place:148]", "features", "[i:place_feature:country]"],
        ["[i:album:album-one]", "country", "[i:place:148]"],
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


def test_shacl_audit_reports_country_without_flag() -> None:
    """Proves the graph contract rejects a country place that carries no flag."""
    triples = make_valid_triples()
    triples.extend([
        ["[i:album:album-one]", "country", "[i:place:187]"],
        ["[i:place:187]", "name", "Las Palmas"],
        ["[i:place:187]", "features", "[i:place_feature:country]"],
    ])

    details = {finding.detail for finding in validate_triples(triples)}

    assert details == {"country must have a flag in things.toml"}


def test_shacl_audit_accepts_country_with_flag() -> None:
    """Proves a named country place with a flag passes the graph contract."""
    triples = make_valid_triples()
    triples.extend([
        ["[i:album:album-one]", "country", "[i:place:186]"],
        ["[i:place:186]", "name", "Gran Canaria"],
        ["[i:place:186]", "flag", "🇮🇨"],
        ["[i:place:186]", "features", "[i:place_feature:country]"],
    ])

    assert validate_triples(triples) == []


def test_shacl_audit_reports_album_without_a_country() -> None:
    """Proves the graph contract requires every album to name a country."""
    triples = [
        triple
        for triple in make_valid_triples()
        if not (triple[0] == "[i:album:album-one]" and triple[1] == "country")
    ]

    details = {finding.detail for finding in validate_triples(triples)}

    assert details == {"album must have at least one country"}


def test_shacl_audit_reports_country_that_is_not_a_country_place() -> None:
    """Proves the graph contract rejects an album country that is a city, not a country."""
    triples = make_valid_triples()
    triples.extend([
        ["[i:album:album-one]", "country", "[i:place:187]"],
        ["[i:place:187]", "name", "Las Palmas"],
        ["[i:place:187]", "flag", "🇮🇨"],
        ["[i:place:187]", "features", "[i:place_feature:city]"],
    ])

    details = {finding.detail for finding in validate_triples(triples)}

    assert details == {"country must be a place with the country feature"}


def test_shacl_audit_reports_album_missing_a_required_field() -> None:
    """Proves the graph contract requires exactly one value for each album field."""
    triples = [
        triple
        for triple in make_valid_triples()
        if not (triple[0] == "[i:album:album-one]" and triple[1] == "mosaic")
    ]

    details = {finding.detail for finding in validate_triples(triples)}

    assert details == {"album must have exactly one mosaic"}


def test_shacl_audit_reports_album_with_non_numeric_count() -> None:
    """Proves the graph contract rejects album counts that are not integer strings."""
    triples = make_valid_triples()
    for triple in triples:
        if triple[:2] == ["[i:album:album-one]", "photosCount"]:
            triple[2] = "many"

    details = {finding.detail for finding in validate_triples(triples)}

    assert details == {"album counts and dates must be non-negative integer strings"}


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


def test_shacl_audit_reports_trip_without_title() -> None:
    """Proves the graph contract rejects a trip that carries no title."""
    triples = make_valid_triples()
    triples.append(["[i:trip:0]", "containsAlbum", "[i:album:album-one]"])

    details = {finding.detail for finding in validate_triples(triples)}

    assert details == {"trip must have exactly one non-empty title"}


def test_shacl_audit_accepts_trip_with_title() -> None:
    """Proves a titled trip passes the graph contract."""
    triples = make_valid_triples()
    triples.extend([
        ["[i:trip:0]", "containsAlbum", "[i:album:album-one]"],
        ["[i:trip:0]", "title", "Gran Canaria, 2026"],
    ])

    assert validate_triples(triples) == []


def test_shacl_audit_reports_trip_with_duplicate_titles() -> None:
    """Proves the graph contract rejects a trip with more than one title."""
    triples = make_valid_triples()
    triples.extend([
        ["[i:trip:0]", "containsAlbum", "[i:album:album-one]"],
        ["[i:trip:0]", "title", "First title"],
        ["[i:trip:0]", "title", "Second title"],
    ])

    details = {finding.detail for finding in validate_triples(triples)}

    assert details == {"trip must have exactly one non-empty title"}
