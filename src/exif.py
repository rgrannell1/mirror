"""Retrieve EXIF information from photo files"""

from functools import lru_cache
from typing import Dict, NotRequired, Required, TypedDict
import warnings

from constants import EXIF_ATTR_ASSOCIATIONS
from PIL import Image, ExifTags


class PhotoExifData(TypedDict):
    """Exif data for a photo"""

    fpath: Required[str]
    created_at: NotRequired[str]
    f_stop: NotRequired[str]
    focal_length: NotRequired[str]
    model: NotRequired[str]
    exposure_time: NotRequired[str]
    iso: NotRequired[str]
    width: NotRequired[str]
    height: NotRequired[str]


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
