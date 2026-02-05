"""Tests for file streaming utilities."""
import io
from utils.file_stream import chunked_read, safe_filename, format_file_size


def test_chunked_read():
    """Test chunked file reading."""
    content = b"x" * 10000  # 10KB of data
    file_obj = io.BytesIO(content)
    
    chunks = list(chunked_read(file_obj, chunk_size=1024))
    
    assert len(chunks) == 10  # 10KB / 1KB = 10 chunks
    assert b"".join(chunks) == content


def test_safe_filename():
    """Test filename sanitization."""
    # Test problematic characters
    assert safe_filename("test/file.txt") == "test_file.txt"
    assert safe_filename("test\\file.txt") == "test_file.txt"
    assert safe_filename("test:file.txt") == "test_file.txt"
    assert safe_filename("test*file.txt") == "test_file.txt"
    
    # Test length truncation
    long_name = "x" * 300 + ".txt"
    result = safe_filename(long_name, max_length=255)
    assert len(result) <= 255
    assert result.endswith(".txt")
    
    # Test normal filename
    assert safe_filename("normal_file.txt") == "normal_file.txt"


def test_format_file_size():
    """Test file size formatting."""
    assert format_file_size(0) == "0.0 B"
    assert format_file_size(1024) == "1.0 KB"
    assert format_file_size(1024 * 1024) == "1.0 MB"
    assert format_file_size(1024 * 1024 * 1024) == "1.0 GB"
    assert format_file_size(500) == "500.0 B"
    assert format_file_size(1536) == "1.5 KB"
