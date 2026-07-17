"""File upload and validation utilities"""
import os
from flask import current_app

def allowed_file(filename, allowed_extensions=None):
    """
    Check if a file has an allowed extension.
    
    Args:
        filename: Name of the file to check
        allowed_extensions: Set of allowed extensions (e.g., {'pdf', 'png', 'jpg'})
                          If None, uses ALLOWED_EXTENSIONS from config
    
    Returns:
        bool: True if file extension is allowed, False otherwise
    """
    if allowed_extensions is None:
        allowed_extensions = current_app.config.get('ALLOWED_EXTENSIONS', {'pdf', 'png', 'jpg', 'jpeg', 'gif'})
    
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_extensions


def allowed_file_size(file, max_size_mb=50):
    """
    Check if a file is within the allowed size limit.
    
    Args:
        file: File object to check
        max_size_mb: Maximum size in megabytes (default: 50MB)
    
    Returns:
        bool: True if file size is acceptable, False otherwise
    """
    file.seek(0, os.SEEK_END)
    size = file.tell()
    file.seek(0)  # Reset file pointer
    return size <= max_size_mb * 1024 * 1024


def get_file_extension(filename):
    """Get the file extension from a filename."""
    return filename.rsplit('.', 1)[1].lower() if '.' in filename else ''


def secure_filename_with_timestamp(filename):
    """Generate a secure filename with timestamp to avoid conflicts."""
    from werkzeug.utils import secure_filename
    from datetime import datetime
    
    name, ext = os.path.splitext(secure_filename(filename))
    timestamp = datetime.utcnow().strftime('%Y%m%d%H%M%S')
    return f"{name}_{timestamp}{ext}"
