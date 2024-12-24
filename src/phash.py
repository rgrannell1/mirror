from typing import NotRequired, Required, TypedDict
from PIL import Image
import imagehash


class PhashData(TypedDict):
    fpath: Required[str]
    phash: NotRequired[str]


class PHashReader:
    @classmethod
    def phash(cls, fpath: str) -> PhashData:
        """Get a perceptual hash from a photo."""

        img = Image.open(fpath)

        return {"fpath": fpath, "phash": str(imagehash.phash(img))}

    @classmethod
    def compare(cls, hash1: str, hash2: str) -> float:
        """Compare two perceptual hashes."""

        return imagehash.hex_to_hash(hash1) - imagehash.hex_to_hash(hash2)

    @classmethod
    def close(cls, hash1: str, hash2: str) -> bool:
        """Check if two perceptual hashes are equal."""
        return cls.compare(hash1, hash2) == 0
