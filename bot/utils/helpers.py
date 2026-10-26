import html
import re
from typing import Union

def format_size(bytes_count: Union[int, float, None]) -> str:
    """Formats bytes into human-readable string (KB, MB, GB)."""
    if not bytes_count or bytes_count <= 0:
        return "Unknown size"
    
    units = ["B", "KB", "MB", "GB", "TB"]
    unit_index = 0
    size = float(bytes_count)
    
    while size >= 1024.0 and unit_index < len(units) - 1:
        size /= 1024.0
        unit_index += 1
        
    return f"{size:.1f} {units[unit_index]}"

def format_duration(seconds: Union[int, float, None]) -> str:
    """Formats duration in seconds to HH:MM:SS or MM:SS."""
    if not seconds or seconds <= 0:
        return "00:00"
    
    seconds = int(seconds)
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"

def sanitize_filename(filename: str, max_length: int = 60) -> str:
    """Removes invalid filesystem characters from filename."""
    if not filename:
        return "media_file"
    # Replace non-alphanumeric (except . - _)
    clean = re.sub(r'[\\/*?:"<>|]', "", filename)
    clean = clean.strip()
    if len(clean) > max_length:
        clean = clean[:max_length].rstrip()
    return clean or "media_file"

def truncate_text(text: str, max_length: int = 100) -> str:
    """Truncates text with ellipsis if it exceeds max_length."""
    if not text:
        return ""
    if len(text) <= max_length:
        return text
    return text[:max_length - 3] + "..."

def safe_html(text: str) -> str:
    """Escapes HTML entities for safe Telegram HTML formatting."""
    if not text:
        return ""
    return html.escape(str(text))
