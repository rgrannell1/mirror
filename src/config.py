
import os
from dotenv import load_dotenv

load_dotenv()

SPACES_REGION = os.getenv('SPACES_REGION')
SPACES_ENDPOINT_URL = os.getenv('SPACES_ENDPOINT_URL')
SPACES_BUCKET = os.getenv('SPACES_BUCKET')
SPACES_ACCESS_KEY_ID = os.getenv('SPACES_ACCESS_KEY_ID')
SPACES_SECRET_KEY = os.getenv('SPACES_SECRET_KEY')
