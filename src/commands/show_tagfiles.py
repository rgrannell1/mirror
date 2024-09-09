import json
from typing import Optional
from src.photo import PhotoVault
from src.constants import ATTR_TAG
from src.tagfile import Tagfile


def show_tagfiles(dir: str, tag: Optional[str] = None) -> None:
    """List all tag-files in a directory."""

    for tagfile in PhotoVault(dir, metadata_path=None).list_tagfiles():
        tag_file = Tagfile.read(tagfile)
        if not tag_file:
            continue

        if not tag_file["images"]:
            continue

        if any(
            image
            for image in tag_file["images"].values()
            if tag in image.get(ATTR_TAG, [])
        ):
            images = tag_file["images"].values()

            tag_file["metadata"] = {
                "fpath": tagfile,
                "total_images": len(images),
                "published": len(
                    [
                        image
                        for image in images
                        if "Published" in image.get(ATTR_TAG, [])
                    ]
                ),
                "untagged_published": len(
                    [image for image in images if len(image.get(ATTR_TAG, [])) == 1]
                ),
            }

            print(json.dumps(tag_file))
