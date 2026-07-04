"""Regression tests for EXIF row construction."""

from mirror.models.exif import ExifReader, PhotoExifData


def test_partial_exif_preserves_created_at(monkeypatch):
    """A file whose EXIF is missing width/height (e.g. Panasonic GH5 stills)
    must still yield a row: dropping the whole row loses created_at, which
    silently removes photographed animals from the checklist first_seen list."""

    partial = {
        "DateTimeOriginal": "2021:10:16 13:42:55",
        "FNumber": "6.3",
        "Model": "DC-GH5",
        "ExposureTime": "0.0025",
        "ISOSpeedRatings": "800",
        # no ExifImageWidth / ExifImageHeight
    }
    monkeypatch.setattr(ExifReader, "raw_exif", classmethod(lambda cls, fpath: partial))

    row = ExifReader.exif("/some/photo.jpg")

    assert row is not None
    assert row.created_at == "2021:10:16 13:42:55"
    assert row.width is None
    assert row.height is None


def test_no_exif_returns_none(monkeypatch):
    """Files with no recognised EXIF tags (GoPro / no-exif) still yield None."""

    monkeypatch.setattr(ExifReader, "raw_exif", classmethod(lambda cls, fpath: {}))

    assert ExifReader.exif("/some/photo.jpg") is None


def test_photo_exif_data_constructs_with_only_fpath():
    """The dataclass must be constructible from fpath alone; optional fields
    default to None rather than raising TypeError."""

    row = PhotoExifData(fpath="/some/photo.jpg")

    assert row.fpath == "/some/photo.jpg"
    assert row.created_at is None
