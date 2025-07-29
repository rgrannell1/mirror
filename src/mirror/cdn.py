"""Interact with the CDN that hosts photos and videos"""

import boto3  # type: ignore
import boto3.session  # type: ignore
import botocore  # type: ignore
from mirror.config import (
    SPACES_REGION,
    SPACES_ENDPOINT_URL,
    SPACES_BUCKET,
    SPACES_ACCESS_KEY_ID,
    SPACES_SECRET_KEY,
)
from mirror.constants import VIDEO_CONTENT_TYPE
from mirror.photo import PhotoContent
from mirror.config import PHOTOS_URL
from mirror.utils import deterministic_hash_str


class CDN:
    """Interface to S3-compatible CDNs"""

    storage_session: boto3.session.Session
    storage_client: boto3.client

    def __init__(self, session: boto3.session.Session = None, client: boto3.client = None):
        self.storage_session = session if session else CDN.session()
        self.storage_client = client if client else CDN.client(self.storage_session)

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
            config=botocore.config.Config(s3={"addressing_style": "virtual"}),
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

    def url(self, key: str) -> str:
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
        """Upload an image to the CDN bucket. Return a CDN link"""
        prefix = deterministic_hash_str(encoded_data.hash() + role)

        name = f"{prefix}.{format}"

        if not self.has_object(name):
            print(f"Uploading {name} to CDN")
            self.upload(name, encoded_data.content)

        return self.url(name)

    def upload_file_public(self, name: str, encoded_path: str) -> str:
        """Upload a file to the CDN"""

        if not encoded_path.startswith("/tmp"):
            raise ValueError(f"Refusing to upload unencoded content {name}")

        if not self.has_object(name):
            print(f"Uploading {name} to CDN")
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
    def video_name(cls, fpath: str, bitrate: str, width: str, height: str, format: str = "mp4") -> str:
        """Return the name of the video in the CDN bucket. It's a deterministic function of
        video parameters"""

        return f"{deterministic_hash_str(f'{fpath}{bitrate}{width}{height}')}.{format}"
