"""Tests for retry logic."""
import pytest
import time
from unittest.mock import Mock, patch
from utils.retry import retry_with_backoff
import requests


def test_retry_on_429():
    """Test retry on HTTP 429 (rate limit)."""
    call_count = [0]
    
    class RateLimitError(requests.RequestException):
        def __init__(self):
            self.response = Mock()
            self.response.status_code = 429
    
    @retry_with_backoff(max_attempts=3, initial_delay=0.1)
    def failing_function():
        call_count[0] += 1
        if call_count[0] < 3:
            raise RateLimitError()
        return "success"
    
    result = failing_function()
    
    assert result == "success"
    assert call_count[0] == 3


def test_retry_on_5xx():
    """Test retry on HTTP 5xx errors."""
    call_count = [0]
    
    class ServerError(requests.RequestException):
        def __init__(self):
            self.response = Mock()
            self.response.status_code = 500
    
    @retry_with_backoff(max_attempts=3, initial_delay=0.1)
    def failing_function():
        call_count[0] += 1
        if call_count[0] < 2:
            raise ServerError()
        return "success"
    
    result = failing_function()
    
    assert result == "success"
    assert call_count[0] == 2


def test_no_retry_on_non_retryable_error():
    """Test that non-retryable errors are not retried."""
    call_count = [0]
    
    class ClientError(Exception):
        pass
    
    @retry_with_backoff(max_attempts=3, initial_delay=0.1)
    def failing_function():
        call_count[0] += 1
        raise ClientError("Non-retryable")
    
    with pytest.raises(ClientError):
        failing_function()
    
    assert call_count[0] == 1  # Should not retry


def test_max_attempts_exceeded():
    """Test that exception is raised after max attempts."""
    call_count = [0]
    
    class ServerError(requests.RequestException):
        def __init__(self):
            self.response = Mock()
            self.response.status_code = 500
    
    @retry_with_backoff(max_attempts=3, initial_delay=0.1)
    def always_failing():
        call_count[0] += 1
        raise ServerError()
    
    with pytest.raises(ServerError):
        always_failing()
    
    assert call_count[0] == 3


def test_exponential_backoff():
    """Test that delays increase exponentially."""
    delays = []
    
    original_sleep = time.sleep
    
    def mock_sleep(seconds):
        delays.append(seconds)
        original_sleep(0)  # Don't actually wait in tests
    
    call_count = [0]
    
    class ServerError(requests.RequestException):
        def __init__(self):
            self.response = Mock()
            self.response.status_code = 500
    
    @retry_with_backoff(max_attempts=3, initial_delay=0.1, backoff_multiplier=2.0)
    def failing_function():
        call_count[0] += 1
        if call_count[0] < 3:
            with patch('time.sleep', mock_sleep):
                raise ServerError()
        return "success"
    
    with patch('time.sleep', mock_sleep):
        failing_function()
    
    # Should have delays: 0.1, 0.2 (exponential backoff)
    assert len(delays) >= 2
    assert delays[0] == pytest.approx(0.1, 0.01)
    assert delays[1] == pytest.approx(0.2, 0.01)
