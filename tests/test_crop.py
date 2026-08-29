"""Prove crop paths and GIMP programs preserve the requested image properties."""

from pathlib import Path

from PIL import Image

from mirror.crop import CropBounds, make_gimp_environment, make_gimp_program, make_output_path
from mirror.crop_gui import make_masked_preview


def test_crop_output_keeps_source_format() -> None:
    """Proves a crop uses a sibling path with the source suffix."""

    cases = [
        (Path("/photos/owl.jpg"), Path("/photos/owl-crop.jpg")),
        (Path("/photos/owl.TIFF"), Path("/photos/owl-crop.TIFF")),
    ]
    for source, expected in cases:
        assert make_output_path(source) == expected


def test_jpeg_crop_uses_exact_bounds_and_best_quality() -> None:
    """Proves GIMP gets exact bounds and highest-quality JPEG settings."""

    bounds = CropBounds(x=12, y=34, width=800, height=600)
    program = make_gimp_program(Path("/photos/owl.jpg"), Path("/photos/owl-crop.jpg"), bounds)

    assert "image.crop(800, 600, 12, 34)" in program
    assert "config.set_property('quality', 1.0)" in program
    assert "config.set_property('sub-sampling', 'sub-sampling-1x1')" in program


def test_gimp_does_not_inherit_the_project_python(monkeypatch) -> None:
    """Proves GIMP uses its system Python instead of the uv environment."""

    monkeypatch.setenv("VIRTUAL_ENV", "/project/.venv")
    monkeypatch.setenv("PATH", "/project/.venv/bin:/usr/bin")

    environment = make_gimp_environment()

    assert "VIRTUAL_ENV" not in environment
    assert environment["PATH"] == "/usr/bin"


def test_crop_preview_blacks_out_eighty_percent() -> None:
    """Proves the preview dims only pixels outside the crop box by 80%."""

    preview = Image.new("RGB", (10, 10), "white")

    masked = make_masked_preview(preview, (2, 2, 8, 8))

    assert masked.getpixel((0, 0)) == (51, 51, 51)
    assert masked.getpixel((5, 5)) == (255, 255, 255)
