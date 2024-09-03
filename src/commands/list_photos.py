import json

import dateparser
from src.photo import PhotoVault


def list_photos(dir: str, metadata_path: str, tag: str, start: str, end: str):
    """List all photos in the directory, as a series of JSON objects. If
    a tag is specified, only list photos with that tag"""

    vault = PhotoVault(dir, metadata_path)

    for image in vault.list_images():
        # skip the image if the tag doesn't match
        if tag and tag not in image.get_xattr_tags():
            continue

        date = image.get_created_date()
        if start:
            start_parsed = dateparser.parse(start)

            if not date or date < start_parsed:
                continue

        if end:
            end_parsed = dateparser.parse(end)

            if not date or date > end_parsed:
                continue

        print(
            json.dumps(
                {
                    "fpath": image.path,
                    "tags": list(image.get_xattr_tags()),
                    "date": str(image.get_created_date()),
                    "description": image.get_xattr_description(),
                    "blur": image.get_blur(),
                }
            )
        )
