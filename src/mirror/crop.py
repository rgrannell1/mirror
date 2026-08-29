"""Crop images through a fixed-ratio desktop selector and GIMP export."""

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class CropBounds:
    """A crop rectangle in source pixels."""

    x: int
    y: int
    width: int
    height: int


def make_output_path(source: Path) -> Path:
    """Return the crop path beside the source, with the same suffix."""

    return source.with_name(f"{source.stem}-crop{source.suffix}")


def make_gimp_program(source: Path, output: Path, bounds: CropBounds) -> str:
    """Build the GIMP Python batch program for one direct export."""

    lines = [
        "from gi.repository import Gio",
        f"source = Gio.File.new_for_path({str(source)!r})",
        f"output = Gio.File.new_for_path({str(output)!r})",
        "image = Gimp.file_load(Gimp.RunMode.NONINTERACTIVE, source)",
        f"image.crop({bounds.width}, {bounds.height}, {bounds.x}, {bounds.y})",
    ]
    if source.suffix.casefold() in {".jpg", ".jpeg"}:
        lines.extend(make_jpeg_export_program())
    else:
        lines.append("assert Gimp.file_save(Gimp.RunMode.NONINTERACTIVE, image, output, None)")
    lines.append("image.delete()")
    return "\n".join(lines)


def make_jpeg_export_program() -> list[str]:
    """Return GIMP statements for its highest-quality JPEG export."""

    properties = {
        "run-mode": "Gimp.RunMode.NONINTERACTIVE",
        "image": "image",
        "file": "output",
        "quality": "1.0",
        "sub-sampling": "'sub-sampling-1x1'",
        "dct": "'float'",
        "include-exif": "True",
        "include-iptc": "True",
        "include-xmp": "True",
        "include-color-profile": "True",
    }
    lines = [
        "procedure = Gimp.get_pdb().lookup_procedure('file-jpeg-export')",
        "config = procedure.create_config()",
    ]
    lines.extend(
        f"config.set_property({name!r}, {value})" for name, value in properties.items()
    )
    lines.extend(
        [
            "result = procedure.run(config)",
            "assert result.index(0) == Gimp.PDBStatusType.SUCCESS",
        ]
    )
    return lines


def export_crop(source: Path, output: Path, bounds: CropBounds) -> None:
    """Ask GIMP to crop and export directly to the output path."""

    executable = shutil.which("gimp-console")
    if executable is None:
        raise RuntimeError("GIMP is not installed")
    program = make_gimp_program(source, output, bounds)
    command = [
        executable,
        "--no-interface",
        "--new-instance",
        "--console-messages",
        "--batch-interpreter=python-fu-eval",
        f"--batch={program}",
        "--quit",
    ]
    subprocess.run(command, check=True, env=make_gimp_environment())


def make_gimp_environment() -> dict[str, str]:
    """Remove uv's Python from the environment inherited by GIMP."""

    environment = os.environ.copy()
    virtual_environment = environment.pop("VIRTUAL_ENV", None)
    if virtual_environment is None:
        return environment
    virtual_bin = str(Path(virtual_environment) / "bin")
    path_parts = environment.get("PATH", "").split(os.pathsep)
    environment["PATH"] = os.pathsep.join(part for part in path_parts if part != virtual_bin)
    return environment


def run_crop_command(image_path: str) -> int:
    """Validate the image and open the crop selector."""

    from mirror.crop_gui import select_crop  # noqa: PLC0415

    source = Path(image_path).expanduser().resolve()
    if not source.is_file():
        raise SystemExit(f"Image does not exist: {source}")
    select_crop(source)
    return 0
