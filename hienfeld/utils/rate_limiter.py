# hienfeld/utils/rate_limiter.py
"""
Rate limiting and retry utilities for LLM API calls.

Provides exponential backoff, batching, and error handling for
robust LLM integration.
"""
import time
import logging
from typing import List, Callable, TypeVar, Any, Optional
from dataclasses import dataclass
from functools import wraps

logger = logging.getLogger(__name__)

T = TypeVar('T')


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""
    max_retries: int = 3
    initial_delay: float = 1.0
    max_delay: float = 60.0
    exponential_base: float = 2.0
    jitter: bool = True


class RateLimitError(Exception):
    """Raised when rate limit is exceeded and retries are exhausted."""
    pass


class LLMError(Exception):
    """Raised when LLM call fails for non-rate-limit reasons."""
    pass


def exponential_backoff(
    attempt: int,
    config: RetryConfig
) -> float:
    """
    Calculate delay for exponential backoff.
    
    Args:
        attempt: Current attempt number (0-indexed)
        config: Retry configuration
        
    Returns:
        Delay in seconds
    """
    delay = config.initial_delay * (config.exponential_base ** attempt)
    delay = min(delay, config.max_delay)
    
    if config.jitter:
        import random
        delay = delay * (0.5 + random.random())
    
    return delay


def with_retry(config: Optional[RetryConfig] = None):
    """
    Decorator for adding retry logic to functions.
    
    Args:
        config: Retry configuration (uses defaults if None)
        
    Returns:
        Decorated function with retry logic
    """
    if config is None:
        config = RetryConfig()
    
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            last_exception = None
            
            for attempt in range(config.max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    error_str = str(e).lower()
                    
                    # Check if it's a rate limit error
                    is_rate_limit = any(term in error_str for term in [
                        'rate limit', 'rate_limit', 'too many requests',
                        '429', 'quota', 'throttl'
                    ])
                    
                    if attempt < config.max_retries:
                        delay = exponential_backoff(attempt, config)
                        
                        if is_rate_limit:
                            logger.warning(
                                f"Rate limit hit, attempt {attempt + 1}/{config.max_retries + 1}. "
                                f"Retrying in {delay:.1f}s..."
                            )
                        else:
                            logger.warning(
                                f"LLM call failed, attempt {attempt + 1}/{config.max_retries + 1}. "
                                f"Error: {e}. Retrying in {delay:.1f}s..."
                            )
                        
                        time.sleep(delay)
                    else:
                        if is_rate_limit:
                            raise RateLimitError(
                                f"Rate limit exceeded after {config.max_retries + 1} attempts"
                            ) from e
                        else:
                            raise LLMError(
                                f"LLM call failed after {config.max_retries + 1} attempts: {e}"
                            ) from e
            
            # Should not reach here, but just in case
            raise last_exception
        
        return wrapper
    return decorator


class BatchProcessor:
    """
    Processes items in batches with rate limiting.
    
    Useful for LLM API calls where you want to process many items
    but need to respect rate limits.
    """
    
    def __init__(
        self,
        batch_size: int = 50,
        delay_between_batches: float = 1.0,
        retry_config: Optional[RetryConfig] = None
    ):
        """
        Initialize batch processor.
        
        Args:
            batch_size: Maximum items per batch
            delay_between_batches: Delay between batches in seconds
            retry_config: Configuration for retry behavior
        """
        self.batch_size = batch_size
        self.delay_between_batches = delay_between_batches
        self.retry_config = retry_config or RetryConfig()
    
    def process(
        self,
        items: List[Any],
        process_func: Callable[[Any], T],
        fallback_func: Optional[Callable[[Any, Exception], T]] = None,
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> List[T]:
        """
        Process items in batches.
        
        Args:
            items: List of items to process
            process_func: Function to process each item
            fallback_func: Optional function to call on failure (item, exception) -> result
            progress_callback: Optional callback(processed, total) for progress updates
            
        Returns:
            List of results (same order as input)
        """
        results = []
        total = len(items)
        
        for batch_start in range(0, total, self.batch_size):
            batch_end = min(batch_start + self.batch_size, total)
            batch = items[batch_start:batch_end]
            
            logger.info(f"Processing batch {batch_start // self.batch_size + 1}: "
                       f"items {batch_start + 1}-{batch_end} of {total}")
            
            for i, item in enumerate(batch):
                try:
                    result = self._process_with_retry(item, process_func)
                    results.append(result)
                except Exception as e:
                    if fallback_func:
                        logger.warning(f"Using fallback for item {batch_start + i + 1}: {e}")
                        result = fallback_func(item, e)
                        results.append(result)
                    else:
                        raise
                
                # Progress update
                if progress_callback:
                    progress_callback(batch_start + i + 1, total)
            
            # Delay between batches (except for last batch)
            if batch_end < total:
                time.sleep(self.delay_between_batches)
        
        return results
    
    def _process_with_retry(
        self,
        item: Any,
        process_func: Callable[[Any], T]
    ) -> T:
        """
        Process a single item with retry logic.
        
        Args:
            item: Item to process
            process_func: Processing function
            
        Returns:
            Processed result
        """
        last_exception = None
        
        for attempt in range(self.retry_config.max_retries + 1):
            try:
                return process_func(item)
            except Exception as e:
                last_exception = e
                
                if attempt < self.retry_config.max_retries:
                    delay = exponential_backoff(attempt, self.retry_config)
                    logger.warning(f"Retry {attempt + 1}: waiting {delay:.1f}s after error: {e}")
                    time.sleep(delay)
        
        raise last_exception


class TokenBucket:
    """
    Token bucket rate limiter for API calls.
    
    Allows burst of requests up to capacity, then limits to rate per second.
    """
    
    def __init__(self, rate: float, capacity: int):
        """
        Initialize token bucket.
        
        Args:
            rate: Tokens added per second
            capacity: Maximum tokens in bucket
        """
        self.rate = rate
        self.capacity = capacity
        self.tokens = capacity
        self.last_update = time.time()
    
    def acquire(self, tokens: int = 1, block: bool = True) -> bool:
        """
        Acquire tokens from the bucket.
        
        Args:
            tokens: Number of tokens to acquire
            block: Whether to block until tokens available
            
        Returns:
            True if tokens acquired, False if not available and not blocking
        """
        while True:
            self._refill()
            
            if self.tokens >= tokens:
                self.tokens -= tokens
                return True
            
            if not block:
                return False
            
            # Calculate wait time
            tokens_needed = tokens - self.tokens
            wait_time = tokens_needed / self.rate
            time.sleep(wait_time)
    
    def _refill(self):
        """Refill tokens based on elapsed time."""
        now = time.time()
        elapsed = now - self.last_update
        self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
        self.last_update = now

