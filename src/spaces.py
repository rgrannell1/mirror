
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

  def upload_image(self, fpath: str) -> bool:
    """Check if a file exists in the Spaces bucket"""

    self.client.upload_file(fpath, SPACES_BUCKET, fpath, ExtraArgs={
      'ACL': 'public-read'
    })

  def list_images(self):
    """List all images in the Spaces bucket"""

    small_selection = self.client.list_objects(Bucket=SPACES_BUCKET)

    for image in small_selection['Contents']:
      yield image
