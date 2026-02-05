"""File streaming utilities for large file transfers."""
import io
from typing import Iterator, Optional


def chunked_read(file_obj: io.BufferedReader, chunk_size: int = 8192) -> Iterator[bytes]:
    """
    Read file in chunks.
    
    Args:
        file_obj: File-like object to read from
        chunk_size: Size of each chunk in bytes
        
    Yields:
        Chunks of bytes
    """
    while True:
        chunk = file_obj.read(chunk_size)
        if not chunk:
            break
        yield chunk


def safe_filename(filename: str, max_length: int = 255) -> str:
    """
    Ensure filename is safe and within length limits.
    
    Args:
        filename: Original filename
        max_length: Maximum filename length
        
    Returns:
        Safe filename
    """
    # Remove or replace problematic characters
    safe = filename.replace("\\", "_").replace("/", "_").replace(":", "_")
    safe = safe.replace("*", "_").replace("?", "_").replace('"', "_")
    safe = safe.replace("<", "_").replace(">", "_").replace("|", "_")
    
    # Truncate if too long (preserve extension)
    if len(safe) > max_length:
        parts = safe.rsplit(".", 1)
        if len(parts) == 2:
            name, ext = parts
            max_name_length = max_length - len(ext) - 1
            safe = name[:max_name_length] + "." + ext
        else:
            safe = safe[:max_length]
    
    return safe


def format_file_size(size_bytes: int) -> str:
    """
    Format file size in human-readable format.
    
    Args:
        size_bytes: Size in bytes
        
    Returns:
        Formatted string (e.g., "1.5 MB")
    """
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} PB"
