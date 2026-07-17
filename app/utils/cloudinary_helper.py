import os
import logging
import cloudinary
import cloudinary.uploader

logger = logging.getLogger(__name__)

# Configures Cloudinary using the CLOUDINARY_URL environment variable
cloudinary_url = os.getenv('CLOUDINARY_URL')
if cloudinary_url:
    cloudinary.config(cloudinary_url=cloudinary_url)
    logger.info("Cloudinary client configured successfully")
else:
    logger.warning("CLOUDINARY_URL env variable not found. Cloudinary operations will fall back to local disk.")

def upload_file_to_cloudinary(file_stream, folder="pace_uploads", resource_type="auto"):
    """
    Uploads a file stream (like a Werkzeug FileStorage object) directly to Cloudinary.
    Returns the secure URL of the uploaded asset, or None if failed.
    """
    if not os.getenv('CLOUDINARY_URL'):
        logger.warning("CLOUDINARY_URL is not set. Skipping Cloudinary upload.")
        return None
        
    try:
        response = cloudinary.uploader.upload(
            file_stream,
            folder=folder,
            resource_type=resource_type
        )
        return response.get('secure_url')
    except Exception as e:
        logger.error(f"Failed to upload to Cloudinary: {str(e)}")
        return None
