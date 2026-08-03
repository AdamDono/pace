import os
import logging

logger = logging.getLogger(__name__)

# Ensure CLOUDINARY_URL starts with 'cloudinary://' before importing the library, 
# otherwise the library's internal initialization will throw a ValueError.
cloudinary_url = os.getenv('CLOUDINARY_URL')
if cloudinary_url and not cloudinary_url.startswith('cloudinary://'):
    logger.warning("CLOUDINARY_URL is missing the 'cloudinary://' prefix. Disabling Cloudinary.")
    os.environ.pop('CLOUDINARY_URL', None)
    cloudinary_url = None

import cloudinary
import cloudinary.uploader

# Configures Cloudinary using the CLOUDINARY_URL environment variable
if cloudinary_url:
    cloudinary.config(cloudinary_url=cloudinary_url)
    logger.info("Cloudinary client configured successfully")
else:
    logger.warning("CLOUDINARY_URL env variable not found or invalid. Cloudinary operations will fall back to local disk.")

def upload_file_to_cloudinary(file_stream, folder="pace_uploads", resource_type="auto"):
    """
    Uploads a file stream directly to Cloudinary.
    Returns the secure URL of the uploaded asset, or None if failed.
    """
    url = os.getenv('CLOUDINARY_URL')
    if not url:
        logger.warning("CLOUDINARY_URL is not set. Skipping Cloudinary upload.")
        return None
        
    try:
        cloudinary.config(cloudinary_url=url)
        response = cloudinary.uploader.upload(
            file_stream,
            folder=folder,
            resource_type=resource_type
        )
        return response.get('secure_url')
    except Exception as e:
        logger.warning(f"Cloudinary upload with resource_type={resource_type} failed ({e}), attempting raw fallback...")
        try:
            if hasattr(file_stream, 'seek'):
                file_stream.seek(0)
            response = cloudinary.uploader.upload(
                file_stream,
                folder=folder,
                resource_type="raw"
            )
            return response.get('secure_url')
        except Exception as err2:
            logger.error(f"Failed to upload to Cloudinary: {err2}")
            return None
