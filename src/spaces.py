"""Interface to DigitalOcean Spaces"""

import boto3
import botocore

from typing import Tuple

from src.photo import ImageContent
from src.utils import deterministic_hash
from .config import (SPACES_REGION, SPACES_ENDPOINT_URL, SPACES_BUCKET,
                     SPACES_ACCESS_KEY_ID, SPACES_SECRET_KEY)
from .constants import (PHOTOS_URL)


class Spaces:
  """Interface to DigitalOcean Spaces"""

  def __init__(self,
               session: boto3.session.Session = None,
               client: boto3.client = None):
    self.session = session if session else Spaces.session()
    self.client = client if client else Spaces.client(self.session)

  @classmethod
  def session(cls):
    """Create a boto3 session for DigitalOcean Spaces"""

    return boto3.session.Session(region_name=SPACES_REGION,
                                 aws_access_key_id=SPACES_ACCESS_KEY_ID,
                                 aws_secret_access_key=SPACES_SECRET_KEY)

  @classmethod
  def client(cls, session: boto3.session.Session):
    """Create a boto3 client for DigitalOcean Spaces"""

    return session.client(
        's3',
        config=botocore.config.Config(s3={'addressing_style': 'virtual'}),
        region_name=SPACES_REGION,
        endpoint_url=SPACES_ENDPOINT_URL,
        aws_access_key_id=SPACES_ACCESS_KEY_ID,
        aws_secret_access_key=SPACES_SECRET_KEY)

  def set_bucket_acl(self):
    """Mark the bucket as public-read"""

    self.client.put_bucket_acl(Bucket=SPACES_BUCKET, ACL='public-read')

  def set_bucket_cors_policy(self):
    """Set the CORS policy for the bucket"""

    self.client.put_bucket_cors(Bucket=SPACES_BUCKET,
                                CORSConfiguration={
                                    'CORSRules': [{
                                        'AllowedHeaders': ['*'],
                                        'AllowedMethods': ['GET'],
                                        'AllowedOrigins': [PHOTOS_URL],
                                        'ExposeHeaders': ['ETag']
                                    }]
                                })

  def upload_public(self,
                    key: str,
                    content: str,
                    mime_type: str = 'image/webp') -> bool:
    """Upload a file publically to S3"""

    return self.client.put_object(
        Body=content,
        Bucket=SPACES_BUCKET,
        Key=key,
        ContentDisposition='inline',
        CacheControl='public, max-age=31536000, immutable',
        ContentType=mime_type,
        ACL='public-read')

  def upload_file_public(self, name: str,
                         encoded_path: str) -> bool:

    return self.client.upload_file(
        Filename=encoded_path,
        Bucket=SPACES_BUCKET,
        Key=name,
        ExtraArgs={
            'ContentDisposition': 'inline',
            'CacheControl': 'public, max-age=31536000, immutable',
            'ContentType': 'video/mp4',
            'ACL': 'public-read'
        }
      )

  def upload_image(self, encoded_data: ImageContent, format='webp'):
    """Upload an image to the Spaces bucket. Return a CDN link"""

    name = f"{encoded_data.hash}.{format}"
    self.upload_public(name, encoded_data.content)

    return f"https://{SPACES_BUCKET}.{SPACES_REGION}.cdn.digitaloceanspaces.com/{name}"

  def upload_video(self, initial_path: str, encoded_path: str, format='mp4'):
    """Upload a video to the Spaces bucket. Return a CDN link"""

    name = f"{deterministic_hash(initial_path)}.{format}"
    self.upload_public(name, open(encoded_path, 'rb').read(), f'video/{format}')

    return f"https://{SPACES_BUCKET}.{SPACES_REGION}.cdn.digitaloceanspaces.com/{name}"

  def upload_thumbnail(self, encoded_data: ImageContent, format='webp'):
    """Upload a thumbnail to the Spaces bucket. Return a CDN link"""

    name = f"{encoded_data.hash}_thumbnail.{format}"
    self.upload_public(name, encoded_data.content)

    return f"https://{SPACES_BUCKET}.{SPACES_REGION}.cdn.digitaloceanspaces.com/{name}"

  def has_object(self, name: str) -> bool:
    """Check if a file exists in the Spaces bucket"""

    try:
      self.client.head_object(Bucket=SPACES_BUCKET, Key=name)
      return True
    except Exception as err:
      if "404" in str(err):
        return False

      raise

  def url(self, name) -> str:
    """Return the CDN URL of a file in the Spaces bucket"""

    return f"https://{SPACES_BUCKET}.{SPACES_REGION}.cdn.digitaloceanspaces.com/{name}"

  def thumbnail_status(self,
                       encoded_image: ImageContent,
                       format='webp') -> Tuple[bool, str]:
    """Check if a thumbnail for an image exists in the Spaces bucket"""

    name = f"{encoded_image.hash}_thumbnail.{format}"

    return self.has_object(name), self.url(name)

  def image_status(self,
                   encoded_image: ImageContent,
                   format='webp') -> Tuple[bool, str]:
    """Check if an image exists in the Spaces bucket"""

    name = f"{encoded_image.hash}.{format}"

    return self.has_object(name), self.url(name)

  @classmethod
  def video_name(cls, fpath: str, format='mp4') -> str:
    """Return the name of the video in the Spaces bucket"""

    return f"{deterministic_hash(fpath)}.{format}"

  def video_status(self, video_name: str) -> Tuple[bool, str]:
    """Check if a video exists in the Spaces bucket"""

    return self.has_object(video_name), self.url(video_name)

  def patch_content_metadata(self, mime_type: str = 'image/webp'):
    """Update the metadata for all objects in the Spaces bucket"""

    objs = self.client.list_objects_v2(Bucket=SPACES_BUCKET)

    # enumerate all objects in the bucket
    for item in objs['Contents']:
      key = item['Key']

      metadata = self.client.head_object(Bucket=SPACES_BUCKET,
                                         Key=key)['Metadata']

      self.client.copy_object(
          Bucket=SPACES_BUCKET,
          Key=key,
          CopySource={
              'Bucket': SPACES_BUCKET,
              'Key': key
          },
          Metadata=metadata,
          MetadataDirective='REPLACE',
          CacheControl='public, max-age=31536000, immutable',
          ContentDisposition='inline',
          ContentType=mime_type,
          ACL='public-read')
