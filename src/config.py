"""Environment variables"""

import os
from typing import Optional
import yaml
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

# DigitalOcean Spaces information
SPACES_REGION = os.getenv("SPACES_REGION")
SPACES_ENDPOINT_URL = os.getenv("SPACES_ENDPOINT_URL")
SPACES_BUCKET = os.getenv("SPACES_BUCKET")
SPACES_ACCESS_KEY_ID = os.getenv("SPACES_ACCESS_KEY_ID")
SPACES_SECRET_KEY = os.getenv("SPACES_SECRET_KEY")


@dataclass
class MirrorConfig:
    """Load XDG configuration from a file."""

    manifest: Optional[str]
    metadata: Optional[str]
    directory: Optional[str]

    @classmethod
    def exists(cls):
        config_path = os.path.expanduser("/home/rg/.config/mirror/config.yaml")
        return os.path.exists(config_path)

    @classmethod
    def read(cls, args):
        config_path = os.path.expanduser("/home/rg/.config/mirror/config.yaml")

        with open(config_path, "r") as file:
            content = yaml.load(file, Loader=yaml.FullLoader)

        return MirrorConfig(
            manifest=content.get("manifest", args.get("<manifest>")),
            metadata=content.get("metadata", args.get("--metadata")),
            directory=content.get("directory", args.get("<dir>")),
        )
