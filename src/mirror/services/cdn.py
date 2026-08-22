"""Interact with the CDN that hosts photos and videos"""

from functools import cache

import boto3  # type: ignore
import boto3.session  # type: ignore
import botocore  # type: ignore

from mirror.commons.config import (
    PHOTOS_URL,
    SPACES_ACCESS_KEY_ID,
    SPACES_BUCKET,
    SPACES_ENDPOINT_URL,
    SPACES_REGION,
    SPACES_SECRET_KEY,
)
from mirror.commons.constants import VIDEO_CONTENT_TYPE
from mirror.commons.utils import deterministic_hash_str
from mirror.models.photo import PhotoContent


class CDN:
    """Interface to S3-compatible CDNs"""

    storage_session: boto3.session.Session
    storage_client: boto3.client

    def __init__(self, session: boto3.session.Session = None, client: boto3.client = None):
        self.storage_session = session if session else shared_session()
        self.storage_client = client if client else shared_client()

    @classmethod
    def session(cls) -> boto3.Session:
        """Create a boto3 session for S$-compatible CDNs"""

        return boto3.session.Session(
            region_name=SPACES_REGION,
            aws_access_key_id=SPACES_ACCESS_KEY_ID,
            aws_secret_access_key=SPACES_SECRET_KEY,
        )

    @classmethod
    def client(cls, session: boto3.session.Session) -> boto3.client:
        """Create a boto3 client for S$-compatible CDNs"""

        return session.client(
            "s3",
            config=botocore.config.Config(
                s3={"addressing_style": "virtual"},
                tcp_keepalive=True,
            ),
            region_name=SPACES_REGION,
            endpoint_url=SPACES_ENDPOINT_URL,
            aws_access_key_id=SPACES_ACCESS_KEY_ID,
            aws_secret_access_key=SPACES_SECRET_KEY,
        )

    def upload(self, key: str, content: bytes, mime_type: str = "image/webp") -> str:
        """Upload a file publically to an S3-compatible CDN"""

        self.storage_client.put_object(
            Body=content,
            Bucket=SPACES_BUCKET,
            Key=key,
            ContentDisposition="inline",
            CacheControl="public, max-age=31536000, immutable",
            ContentType=mime_type,
            ACL="public-read",
        )

        return self.url(key)

    @staticmethod
    def url(key: str) -> str:
        return f"{PHOTOS_URL}/{key}"

    def has_object(self, name: str) -> bool:
        """Does the object already exist in the bucket?"""

        try:
            self.storage_client.head_object(Bucket=SPACES_BUCKET, Key=name)
            return True
        except self.storage_client.exceptions.ClientError as err:
            if err.response["Error"]["Code"] == "404":
                return False
            else:
                raise

    def upload_photo(self, encoded_data: PhotoContent, role: str, format: str = "webp") -> str:
        """Upload an image to the CDN bucket. Return a CDN link.

        Photo names are content-addressed, so a repeat upload overwrites identical
        bytes. Uploading without a HEAD check halves the round trips per photo."""
        prefix = deterministic_hash_str(encoded_data.hash() + role)

        name = f"{prefix}.{format}"

        self.upload(name, encoded_data.content, mime_type=f"image/{format}")

        return self.url(name)

    # NOTE: this is an extreme bottleneck, and is more often than not used on a bad WiFi connection
    # on my half-defective laptop wifi
    def upload_file_public(self, name: str, encoded_path: str) -> str:
        """Upload a file to the CDN"""

        if not encoded_path.startswith("/tmp"):
            raise ValueError(f"Refusing to upload unencoded content {name}")

        if not self.has_object(name):
            self.storage_client.upload_file(
                Filename=encoded_path,
                Bucket=SPACES_BUCKET,
                Key=name,
                ExtraArgs={
                    "ContentDisposition": "inline",
                    "CacheControl": "public, max-age=31536000, immutable",
                    "ContentType": VIDEO_CONTENT_TYPE,
                    "ACL": "public-read",
                },
            )

        return self.url(name)

    @classmethod
    def video_name(cls, fpath: str, params: dict, format: str = "mp4") -> str:
        """Return the name of the video in the CDN bucket. It's a deterministic function of
        video parameters"""

        bitrate, width, height = params["bitrate"], params["width"], params["height"]
        return f"{deterministic_hash_str(f'{fpath}{bitrate}{width}{height}')}.{format}"


@cache
def shared_session() -> boto3.session.Session:
    """One boto3 session per process, shared across jobs."""

    return CDN.session()


@cache
def shared_client() -> boto3.client:
    """One S3 client per process. Reuse keeps the TLS connection alive between uploads."""

    return CDN.client(shared_session())
