import cv2
import numpy as np
from PIL import Image, ImageOps
import hashlib
import io
import tempfile
import subprocess
import os
import yaml

window_size = 200  # Adjust this value as needed
THUMBNAIL_WIDTH = 400  # Example width, adjust as needed
THUMBNAIL_HEIGHT = 400  # Example height, adjust as needed
ASPECT_RATIO = THUMBNAIL_WIDTH / THUMBNAIL_HEIGHT


class ImageContent:

  def __init__(self, hash, content):
    self.hash = hash
    self.content = content


def variance_of_laplacian(image):
  """Compute the Laplacian of the image and return the variance."""
  return cv2.Laplacian(image, cv2.CV_64F).var()


def sharpest_region(image, window_size):
  """Find the coordinates of the sharpest region in the image."""
  gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
  height, width = gray.shape

  max_variance = 0
  sharpest_x, sharpest_y = 0, 0

  for y in range(0, height - window_size + 1, window_size):
    for x in range(0, width - window_size + 1, window_size):
      window = gray[y:y + window_size, x:x + window_size]
      variance = variance_of_laplacian(window)
      if variance > max_variance:
        max_variance = variance
        sharpest_x, sharpest_y = x, y

  return sharpest_x, sharpest_y


def crop_centered_on_sharpest(img, aspect_ratio, thumb_height):
  # Convert the PIL image to a format compatible with OpenCV
  open_cv_image = np.array(img)
  open_cv_image = open_cv_image[:, :, ::-1].copy()  # Convert RGB to BGR

  # Define the window size for sharpness detection

  # Get the coordinates of the sharpest region
  sharpest_x, sharpest_y = sharpest_region(open_cv_image, window_size)

  # Calculate the center of the sharpest region
  center_x = sharpest_x + window_size // 2
  center_y = sharpest_y + window_size // 2

  # Calculate the cropping box to maintain aspect ratio and include full height
  img_height = img.height
  img_width = img.width
  crop_width = int(aspect_ratio * img_height)

  left = max(center_x - crop_width // 2, 0)
  right = min(left + crop_width, img_width)

  if right - left < crop_width:
    left = right - crop_width

  # Crop the image
  return img.crop((left, 0, right, img_height))


class ImageProcessor:

  def __init__(self, path):
    self.path = path

  def encode_thumbnail(self, centered_on_sharpest=False) -> ImageContent:
    """Encode an image as a thumbnail WebP, and remove EXIF data"""
    img = Image.open(self.path)
    img = img.convert('RGB')

    if centered_on_sharpest:
      # Crop around the sharpest region and then resize to the thumbnail size
      cropped_img = crop_centered_on_sharpest(img, ASPECT_RATIO,
                                              THUMBNAIL_HEIGHT)
      thumb = ImageOps.fit(cropped_img, (THUMBNAIL_WIDTH, THUMBNAIL_HEIGHT))
    else:
      # Use the original method to resize the image to the thumbnail size
      thumb = ImageOps.fit(img, (THUMBNAIL_WIDTH, THUMBNAIL_HEIGHT))

    # Remove EXIF data from the image by cloning
    data = list(thumb.getdata())
    no_exif = Image.new(thumb.mode, thumb.size)
    no_exif.putdata(data)

    with io.BytesIO() as output:
      # Return the image hash and contents
      no_exif.save(output, format="WEBP", lossless=True)
      contents = output.getvalue()

      hasher = hashlib.new('sha256')
      hasher.update(contents)

      return ImageContent(hash=hasher.hexdigest(), content=contents)


# Function to display thumbnail images side by side using GNOME's Image Viewer


def display_images_with_eog(thumb_original, thumb_sharpest):
  thumb_original = cv2.cvtColor(np.array(thumb_original), cv2.COLOR_RGB2BGR)
  thumb_sharpest = cv2.cvtColor(np.array(thumb_sharpest), cv2.COLOR_RGB2BGR)

  # Pad the thumbnails to match the height of the taller thumbnail
  height_thumb_original = thumb_original.shape[0]
  height_thumb_sharpest = thumb_sharpest.shape[0]

  max_height = max(height_thumb_original, height_thumb_sharpest)

  if max_height > height_thumb_original:
    padding = max_height - height_thumb_original
    thumb_original = cv2.copyMakeBorder(thumb_original, 0, padding, 0, 0,
                                        cv2.BORDER_CONSTANT)

  if max_height > height_thumb_sharpest:
    padding = max_height - height_thumb_sharpest
    thumb_sharpest = cv2.copyMakeBorder(thumb_sharpest, 0, padding, 0, 0,
                                        cv2.BORDER_CONSTANT)

  # Create a combined image
  combined_image = np.hstack((thumb_original, thumb_sharpest))

  # Save the combined image to a temporary file
  temp_file = tempfile.NamedTemporaryFile(suffix='.png', delete=False)
  cv2.imwrite(temp_file.name, combined_image)

  # Open the combined image with GNOME's Image Viewer
  subprocess.run(['eog', temp_file.name])


def save_comparison_image(output_folder, image_name, thumb_original,
                          thumb_sharpest):
  thumb_original = cv2.cvtColor(np.array(thumb_original), cv2.COLOR_RGB2BGR)
  thumb_sharpest = cv2.cvtColor(np.array(thumb_sharpest), cv2.COLOR_RGB2BGR)

  # Pad the thumbnails to match the height of the taller thumbnail
  height_thumb_original = thumb_original.shape[0]
  height_thumb_sharpest = thumb_sharpest.shape[0]

  max_height = max(height_thumb_original, height_thumb_sharpest)

  if max_height > height_thumb_original:
    padding = max_height - height_thumb_original
    thumb_original = cv2.copyMakeBorder(thumb_original, 0, padding, 0, 0,
                                        cv2.BORDER_CONSTANT)

  if max_height > height_thumb_sharpest:
    padding = max_height - height_thumb_sharpest
    thumb_sharpest = cv2.copyMakeBorder(thumb_sharpest, 0, padding, 0, 0,
                                        cv2.BORDER_CONSTANT)

  # Create a combined image
  combined_image = np.hstack((thumb_original, thumb_sharpest))

  # Save the combined image to the output folder
  output_path = os.path.join(output_folder, image_name)
  cv2.imwrite(output_path, combined_image)


def process_photos(root_folder, output_folder):
  # Ensure the output folder exists
  os.makedirs(output_folder, exist_ok=True)

  for root, dirs, files in os.walk(root_folder):
    if 'Photos from' in root:
      continue
    # Check for the presence of tags.md in the current directory
    if 'tags.md' in files:

      tags_path = os.path.join(root, 'tags.md')
      with open(tags_path, 'r') as file:
        tags_data = yaml.safe_load(file)[0]

      album_cover = tags_data.get('user.xyz.rgrannell.photos.album_cover')

      for file in files:
        if file.lower().endswith(('jpg', 'jpeg', 'png')):

          if album_cover and album_cover != file:
            continue

          image_path = os.path.join(root, file)
          processor = ImageProcessor(image_path)

          # Generate the original thumbnail and the new method thumbnail
          thumbnail_original = processor.encode_thumbnail(
              centered_on_sharpest=False)
          thumbnail_sharpest = processor.encode_thumbnail(
              centered_on_sharpest=True)

          # Load the thumbnail images
          thumb_original_image = Image.open(
              io.BytesIO(thumbnail_original.content))
          thumb_sharpest_image = Image.open(
              io.BytesIO(thumbnail_sharpest.content))

          # Save the comparison image to the output folder
          save_comparison_image(output_folder,
                                f"{os.path.splitext(file)[0]}_comparison.png",
                                thumb_original_image, thumb_sharpest_image)
          print(f"Processed {image_path}")


# Example usage
process_photos("/home/rg/Drive/Photos", "/home/rg/Desktop/AB-test")
