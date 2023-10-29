
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
    self.session = boto3.session.Session(
      region_name=SPACES_REGION,
      aws_access_key_id=SPACES_ACCESS_KEY_ID,
      aws_secret_access_key=SPACES_SECRET_KEY
    )
    self.client = self.session.client(
      's3',
      config=botocore.config.Config(s3={'addressing_style': 'virtual'}),
      region_name=SPACES_REGION,
      endpoint_url=SPACES_ENDPOINT_URL,
      aws_access_key_id=SPACES_ACCESS_KEY_ID,
      aws_secret_access_key=SPACES_SECRET_KEY)

  def set_acl(self):
    self.client.put_bucket_acl(Bucket=SPACES_BUCKET, ACL='public-read')

  def upload(self, key: str, content: str) -> bool:
    """Check if a file exists in the Spaces bucket"""

    return self.client.put_object(Body=content, Bucket=SPACES_BUCKET, Key=key, ACL='public-read')

  def list_images(self):
    """List all images in the Spaces bucket"""

    small_selection = self.client.list_objects(Bucket=SPACES_BUCKET)

    for image in small_selection['Contents']:
      yield image

  def upload_image(self, encoded_data):
    """Upload an image to the Spaces bucket"""
    name = f"{encoded_data['hash']}.webp"
    self.upload(name, encoded_data['content'])

    return f"https://{SPACES_BUCKET}.{SPACES_REGION}.digitaloceanspaces.com/{name}"

  def upload_thumbnail(self, encoded_data):
    """Upload a thumbnail to the Spaces bucket"""
    name = f"{encoded_data['hash']}_thumbnail.webp"
    self.upload(name, encoded_data['content'])

    return f"https://{SPACES_BUCKET}.{SPACES_REGION}.digitaloceanspaces.com/{name}"

  def has_file(self, name):
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

  def has_thumbnail(self, encoded_data):
    """Check if a thumbnail for an image exists in the Spaces bucket"""
    name = f"{encoded_data['hash']}_thumbnail.webp"

    return self.has_file(name), self.url(name)

  def has_image(self, encoded_data):
    """Check if an image exists in the Spaces bucket"""

    name = f"{encoded_data['hash']}.webp"

    return self.has_file(name), self.url(name)
