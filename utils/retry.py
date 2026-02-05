"""Retry logic with exponential backoff."""
import time
import logging
from typing import Callable, TypeVar, Optional
from functools import wraps

T = TypeVar("T")
logger = logging.getLogger(__name__)


def retry_with_backoff(
    max_attempts: int = 3,
    initial_delay: float = 1.0,
    max_delay: float = 60.0,
    backoff_multiplier: float = 2.0,
    retryable_status_codes: Optional[list[int]] = None,
):
    """
    Decorator for retrying function calls with exponential backoff.
    
    Args:
        max_attempts: Maximum number of retry attempts (default: 3)
        initial_delay: Initial delay in seconds (default: 1.0)
        max_delay: Maximum delay in seconds (default: 60.0)
        backoff_multiplier: Multiplier for exponential backoff (default: 2.0)
        retryable_status_codes: HTTP status codes to retry (default: [429, 500, 502, 503, 504])
    
    Returns:
        Decorated function
    """
    if retryable_status_codes is None:
        retryable_status_codes = [429, 500, 502, 503, 504]
    
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            delay = initial_delay
            last_exception = None
            
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    
                    # Check if this is a retryable HTTP error
                    should_retry = False
                    if hasattr(e, "response") and hasattr(e.response, "status_code"):
                        status_code = e.response.status_code
                        if status_code in retryable_status_codes:
                            should_retry = True
                            logger.warning(
                                f"HTTP {status_code} error on attempt {attempt}/{max_attempts} "
                                f"for {func.__name__}: {str(e)}"
                            )
                    elif "429" in str(e) or "5" in str(e)[:3]:  # Heuristic for rate limit/5xx
                        should_retry = True
                        logger.warning(
                            f"Retryable error on attempt {attempt}/{max_attempts} "
                            f"for {func.__name__}: {str(e)}"
                        )
                    else:
                        # Non-retryable error
                        logger.error(
                            f"Non-retryable error in {func.__name__}: {str(e)}"
                        )
                        raise
                    
                    if not should_retry or attempt >= max_attempts:
                        raise
                    
                    # Wait before retry
                    logger.info(
                        f"Retrying {func.__name__} after {delay:.1f}s "
                        f"(attempt {attempt + 1}/{max_attempts})"
                    )
                    time.sleep(delay)
                    delay = min(delay * backoff_multiplier, max_delay)
            
            # Should never reach here, but just in case
            if last_exception:
                raise last_exception
            raise RuntimeError(f"Failed after {max_attempts} attempts")
        
        return wrapper
    return decorator
