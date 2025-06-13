"""Retrieve EXIF information from photo files"""

from dataclasses import dataclass
from functools import lru_cache
from typing import Dict, List, NotRequired, Optional, TypedDict
import warnings

from src.constants import EXIF_ATTR_ASSOCIATIONS
from PIL import Image, ExifTags

from src.model import IModel


@dataclass
class PhotoExifData(IModel):
    """Exif data for a photo"""

    fpath: str
    created_at: Optional[str]
    f_stop: Optional[str]
    focal_length: Optional[str]
    model: Optional[str]
    exposure_time: Optional[str]
    iso: Optional[str]
    width: Optional[str]
    height: Optional[str]

    @classmethod
    def from_row(cls, row: List) -> "PhotoExifData":
        """Create a PhotoExifData object from a database row"""

        (fpath, created_at, f_stop, focal_length, model, exposure_time, iso, width, height) = row

        return PhotoExifData(
            fpath=fpath,
            created_at=created_at,
            f_stop=f_stop,
            focal_length=focal_length,
            model=model,
            exposure_time=exposure_time,
            iso=iso,
            width=width,
            height=height,
        )


class ExifReader:
    """Read EXIF data from a photo file"""

    @classmethod
    @lru_cache(maxsize=10)
    def raw_exif(cls, fpath: str) -> Dict:
        """Get EXIF data from a photo."""

        try:
            # ignore image warnings, not all exif will be valid
            with warnings.catch_warnings():
                warnings.filterwarnings("ignore")

                img = Image.open(fpath)
                exif_data = img._getexif()  # type: ignore
        except BaseException:
            return {}

        if not exif_data:
            return {}

        output_exif = {}

        for key, val in exif_data.items():
            if key in ExifTags.TAGS:
                output_exif[ExifTags.TAGS[key]] = val
            else:
                output_exif[key] = val

        return output_exif

    @classmethod
    def exif(cls, fpath: str) -> PhotoExifData:
        """Get interesting EXIF data from a photo."""

        data = {}

        exif_data = cls.raw_exif(fpath)
        for exif_key, dict_key in EXIF_ATTR_ASSOCIATIONS.items():
            if exif_key not in exif_data:
                continue

            if exif_key == "Model":
                data[dict_key] = exif_data[exif_key].strip()
            else:
                data[dict_key] = str(exif_data[exif_key])

        return PhotoExifData(**data, fpath=fpath)  # type: ignore
