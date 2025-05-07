# app/utils.py
from urllib.parse import urlparse

def embed_video_url(url):
    """Convert YouTube URLs to embed format"""
    if 'youtube.com' in url:
        video_id = urlparse(url).query.split('v=')[1]
        return f"https://www.youtube.com/embed/{video_id}"
    return url