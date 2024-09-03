from src.photo import PhotoVault


def list_tagfiles(dir: str, tag: str = None):
    """List all tag-files in a directory."""

    for tagfile in PhotoVault(dir, metadata_path=None).list_tagfiles():
        print(tagfile)
