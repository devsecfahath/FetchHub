import re
from typing import List, Optional, Tuple
from dataclasses import dataclass

@dataclass
class MediaTarget:
    url: str
    platform: str
    platform_name: str
    is_valid: bool

# Platform detection patterns
PATTERNS = {
    "youtube": re.compile(
        r'(https?://)?(www\.|m\.|music\.)?(youtube\.com/(watch\?v=|shorts/|playlist\?|embed/)|youtu\.be/)[a-zA-Z0-9_-]+',
        re.IGNORECASE
    ),
    "instagram": re.compile(
        r'(https?://)?(www\.)?instagram\.com/(p|reel|reels|tv|stories)/[a-zA-Z0-9_-]+',
        re.IGNORECASE
    ),
    "tiktok": re.compile(
        r'(https?://)?(www\.|vm\.|vt\.)?tiktok\.com/(@[a-zA-Z0-9_.-]+/video/\d+|[a-zA-Z0-9_-]+)',
        re.IGNORECASE
    ),
    "facebook": re.compile(
        r'(https?://)?(www\.|m\.|web\.)?(facebook\.com|fb\.watch)/.+',
        re.IGNORECASE
    ),
    "twitter": re.compile(
        r'(https?://)?(www\.)?(twitter\.com|x\.com)/[a-zA-Z0-9_]+/status/\d+',
        re.IGNORECASE
    ),
}

# Generic URL pattern to capture other links (Reddit, Pinterest, SoundCloud, Vimeo, etc.)
GENERIC_URL_PATTERN = re.compile(
    r'https?://[^\s<>"]+|www\.[^\s<>"]+',
    re.IGNORECASE
)

PLATFORM_LABELS = {
    "youtube": "YouTube",
    "instagram": "Instagram",
    "tiktok": "TikTok",
    "facebook": "Facebook",
    "twitter": "X (Twitter)",
    "generic": "Web Media"
}

def clean_media_url(raw_url: str) -> str:
    """Cleans tracking query parameters from social media links."""
    clean = raw_url.strip().rstrip(".,;:!?)>")
    if not clean.startswith("http://") and not clean.startswith("https://"):
        clean = "https://" + clean
    
    # Remove tracking query parameters like igsh, utm_*, fbclid
    # But keep ?v= on youtube or ?v= on facebook
    if "instagram.com" in clean or "tiktok.com" in clean:
        clean = clean.split("?")[0]
        if not clean.endswith("/"):
            clean += "/"
    return clean

def extract_urls(text: str) -> List[str]:
    """Finds all URLs inside a text message."""
    if not text:
        return []
    matches = GENERIC_URL_PATTERN.findall(text)
    urls = []
    for match in matches:
        urls.append(clean_media_url(match))
    return urls

def detect_platform(url: str) -> Tuple[str, str]:
    """
    Detects the platform for a given URL.
    Returns (platform_key, platform_display_name).
    """
    for platform, pattern in PATTERNS.items():
        if pattern.search(url):
            return platform, PLATFORM_LABELS[platform]
    return "generic", PLATFORM_LABELS["generic"]

def inspect_url(url: str) -> Optional[MediaTarget]:
    """Inspects a single URL and returns a MediaTarget."""
    if not url:
        return None
    
    clean_url = url.strip().rstrip(".,;:!?)>")
    if not clean_url.startswith("http://") and not clean_url.startswith("https://"):
        clean_url = "https://" + clean_url

    platform, platform_name = detect_platform(clean_url)
    return MediaTarget(
        url=clean_url,
        platform=platform,
        platform_name=platform_name,
        is_valid=True
    )
