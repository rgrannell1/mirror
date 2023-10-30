"""Interface to DigitalOcean Spaces"""

import boto3
import botocore

from .config import (
  SPACES_REGION,
  SPACES_ENDPOINT_URL,
  SPACES_BUCKET,
  SPACES_ACCESS_KEY_ID,
  SPACES_SECRET_KEY
)

class Spaces:
  """Interface to DigitalOcean Spaces"""

  def __init__(self):
    self.session = Spaces.session()
    self.client = Spaces.client(self.session)

  @classmethod
  def session(cls):
    return boto3.session.Session(
      region_name=SPACES_REGION,
      aws_access_key_id=SPACES_ACCESS_KEY_ID,
      aws_secret_access_key=SPACES_SECRET_KEY
    )

  @classmethod
  def client(cls, session):
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

  def upload_public(self, key: str, content: str) -> bool:
    """Check if a file exists in the Spaces bucket"""

    return self.client.put_object(
      Body=content,
      Bucket=SPACES_BUCKET,
      Key=key,
      ContentDisposition='inline',
      CacheControl='public, max-age=31536000, immutable',
      ACL='public-read')

  def upload_image(self, encoded_data):
    """Upload an image to the Spaces bucket"""

    name = f"{encoded_data['hash']}.webp"
    self.upload_public(name, encoded_data['content'])

    return f"https://{SPACES_BUCKET}.{SPACES_REGION}.digitaloceanspaces.com/{name}"

  def upload_thumbnail(self, encoded_data):
    """Upload a thumbnail to the Spaces bucket"""

    name = f"{encoded_data['hash']}_thumbnail.webp"
    self.upload_public(name, encoded_data['content'])

    return f"https://{SPACES_BUCKET}.{SPACES_REGION}.digitaloceanspaces.com/{name}"

  def has_object(self, name):
    """Check if a file exists in the Spaces bucket"""

    try:
      self.client.head_object(Bucket=SPACES_BUCKET, Key=name)
      return True
    except Exception as err:
      if "404" in str(err):
        return False
      else:
        raise

  def url(self, name) -> str:
    """Return the URL of a file in the Spaces bucket"""

    return f"https://{SPACES_BUCKET}.{SPACES_REGION}.digitaloceanspaces.com/{name}"

  def thumbnail_status(self, encoded_image) -> (bool, str):
    """Check if a thumbnail for an image exists in the Spaces bucket"""

    name = f"{encoded_image['hash']}_thumbnail.webp"

    return self.has_object(name), self.url(name)

  def image_status(self, encoded_image) -> (bool, str):
    """Check if an image exists in the Spaces bucket"""

    name = f"{encoded_image['hash']}.webp"

    return self.has_object(name), self.url(name)
