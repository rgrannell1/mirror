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
    """Create a boto3 session for DigitalOcean Spaces"""

    return boto3.session.Session(
      region_name=SPACES_REGION,
      aws_access_key_id=SPACES_ACCESS_KEY_ID,
      aws_secret_access_key=SPACES_SECRET_KEY
    )

  @classmethod
  def client(cls, session):
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

    self.client.put_bucket_cors(
      Bucket=SPACES_BUCKET,
      CORSConfiguration={
        'CORSRules': [
          {
            'AllowedHeaders': ['*'],
            'AllowedMethods': ['GET'],
            'AllowedOrigins': ['https://photos.rgrannell.xyz'],
            'ExposeHeaders': ['ETag']
          }
        ]
      })

  def upload_public(self, key: str, content: str) -> bool:
    """Check if a file exists in the Spaces bucket"""

    return self.client.put_object(
      Body=content,
      Bucket=SPACES_BUCKET,
      Key=key,
      ContentDisposition='inline',
      CacheControl='public, max-age=31536000, immutable',
      ContentType='image/webp',
      ACL='public-read')

  def upload_image(self, encoded_data):
    """Upload an image to the Spaces bucket"""

    name = f"{encoded_data['hash']}.webp"
    self.upload_public(name, encoded_data['content'])

    return f"https://{SPACES_BUCKET}.{SPACES_REGION}.cdn.digitaloceanspaces.com/{name}"

  def upload_thumbnail(self, encoded_data):
    """Upload a thumbnail to the Spaces bucket"""

    name = f"{encoded_data['hash']}_thumbnail.webp"
    self.upload_public(name, encoded_data['content'])

    return f"https://{SPACES_BUCKET}.{SPACES_REGION}.cdn.digitaloceanspaces.com/{name}"

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

    return f"https://{SPACES_BUCKET}.{SPACES_REGION}.cdn.digitaloceanspaces.com/{name}"

  def thumbnail_status(self, encoded_image) -> (bool, str):
    """Check if a thumbnail for an image exists in the Spaces bucket"""

    name = f"{encoded_image['hash']}_thumbnail.webp"

    return self.has_object(name), self.url(name)

  def image_status(self, encoded_image) -> (bool, str):
    """Check if an image exists in the Spaces bucket"""

    name = f"{encoded_image['hash']}.webp"

    return self.has_object(name), self.url(name)

  def patch_content_metadata(self):
    """Update the metadata for all objects in the Spaces bucket"""

    objs = self.client.list_objects_v2(Bucket=SPACES_BUCKET)

    # enumerate all objects in the bucket
    for item in objs['Contents']:
      key = item['Key']

      metadata = self.client.head_object(Bucket=SPACES_BUCKET, Key=key)['Metadata']

      self.client.copy_object(
        Bucket=SPACES_BUCKET,
        Key=key,
        CopySource={'Bucket': SPACES_BUCKET, 'Key': key},
        Metadata=metadata,
        MetadataDirective='REPLACE',
        CacheControl='public, max-age=31536000, immutable',
        ContentDisposition='inline',
        ContentType='image/webp',
        ACL='public-read'
      )
