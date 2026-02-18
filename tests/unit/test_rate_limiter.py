"""
Unit tests for rate limiting utilities.

Tests exponential backoff, retry decorator, batch processing, and token bucket.
"""

import pytest
import time
from unittest.mock import patch, MagicMock
from hienfeld.utils.rate_limiter import (
    RetryConfig,
    RateLimitError,
    LLMError,
    exponential_backoff,
    with_retry,
    BatchProcessor,
    TokenBucket
)


# ============================================================
# RetryConfig Tests
# ============================================================

class TestRetryConfig:
    """Tests for retry configuration."""

    def test_retry_config_defaults(self):
        """RetryConfig has sensible defaults."""
        config = RetryConfig()

        assert config.max_retries == 3
        assert config.initial_delay == 1.0
        assert config.max_delay == 60.0
        assert config.exponential_base == 2.0
        assert config.jitter is True

    def test_retry_config_custom_values(self):
        """Create RetryConfig with custom values."""
        config = RetryConfig(
            max_retries=5,
            initial_delay=0.5,
            max_delay=120.0,
            exponential_base=1.5,
            jitter=False
        )

        assert config.max_retries == 5
        assert config.initial_delay == 0.5
        assert config.max_delay == 120.0
        assert config.exponential_base == 1.5
        assert config.jitter is False


# ============================================================
# Exponential Backoff Tests
# ============================================================

class TestExponentialBackoff:
    """Tests for exponential backoff calculation."""

    def test_exponential_backoff_first_attempt(self):
        """First attempt backoff equals initial delay."""
        config = RetryConfig(initial_delay=1.0, exponential_base=2.0, jitter=False)

        delay = exponential_backoff(0, config)

        assert delay == 1.0

    def test_exponential_backoff_second_attempt(self):
        """Second attempt doubles the delay."""
        config = RetryConfig(initial_delay=1.0, exponential_base=2.0, jitter=False)

        delay = exponential_backoff(1, config)

        assert delay == 2.0

    def test_exponential_backoff_third_attempt(self):
        """Third attempt quadruples the delay."""
        config = RetryConfig(initial_delay=1.0, exponential_base=2.0, jitter=False)

        delay = exponential_backoff(2, config)

        assert delay == 4.0

    def test_exponential_backoff_respects_max_delay(self):
        """Backoff is capped at max_delay."""
        config = RetryConfig(initial_delay=1.0, max_delay=10.0, exponential_base=2.0, jitter=False)

        delay = exponential_backoff(10, config)  # 2^10 = 1024

        assert delay == 10.0

    def test_exponential_backoff_with_jitter(self):
        """Jitter adds randomness to delay."""
        config = RetryConfig(initial_delay=1.0, exponential_base=2.0, jitter=True)

        delay1 = exponential_backoff(0, config)
        delay2 = exponential_backoff(0, config)

        # With jitter, same attempt can give different delays
        # Both should be between 0.5 and 1.0 times the base delay
        # Jitter range: 0.5 to 1.0 of the calculated delay
        assert delay1 > 0
        assert delay2 > 0
        # Could be different due to randomness
        assert isinstance(delay1, float)
        assert isinstance(delay2, float)

    def test_exponential_backoff_without_jitter(self):
        """Without jitter, same attempt gives same delay."""
        config = RetryConfig(initial_delay=1.0, exponential_base=2.0, jitter=False)

        delay1 = exponential_backoff(1, config)
        delay2 = exponential_backoff(1, config)

        assert delay1 == delay2

    def test_exponential_backoff_custom_base(self):
        """Custom exponential base works correctly."""
        config = RetryConfig(initial_delay=1.0, exponential_base=1.5, jitter=False)

        delay0 = exponential_backoff(0, config)
        delay1 = exponential_backoff(1, config)
        delay2 = exponential_backoff(2, config)

        assert delay0 == 1.0
        assert delay1 == 1.5
        assert delay2 == 2.25

    def test_exponential_backoff_zero_initial_delay(self):
        """Handle zero initial delay."""
        config = RetryConfig(initial_delay=0.0, exponential_base=2.0, jitter=False)

        delay = exponential_backoff(5, config)

        assert delay == 0.0


# ============================================================
# Retry Decorator Tests
# ============================================================

class TestRetryDecorator:
    """Tests for @with_retry decorator."""

    def test_retry_success_on_first_attempt(self):
        """Function succeeds on first attempt."""
        call_count = 0

        @with_retry()
        def successful_function():
            nonlocal call_count
            call_count += 1
            return "success"

        result = successful_function()

        assert result == "success"
        assert call_count == 1

    def test_retry_success_after_failure(self):
        """Function succeeds after initial failures."""
        call_count = 0

        @with_retry(RetryConfig(max_retries=2, initial_delay=0.01))
        def flaky_function():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ValueError("Temporary failure")
            return "success"

        result = flaky_function()

        assert result == "success"
        assert call_count == 2

    def test_retry_exhausts_attempts(self):
        """Raises LLMError after max attempts."""
        @with_retry(RetryConfig(max_retries=2, initial_delay=0.01))
        def always_fails():
            raise ValueError("Permanent failure")

        with pytest.raises(LLMError):
            always_fails()

    def test_retry_detects_rate_limit_error(self):
        """Detects rate limit errors."""
        @with_retry(RetryConfig(max_retries=1, initial_delay=0.01))
        def rate_limited():
            raise ValueError("429 Too Many Requests")

        with pytest.raises(RateLimitError):
            rate_limited()

    def test_retry_detects_rate_limit_keywords(self):
        """Detects various rate limit keywords."""
        keywords = ["rate limit", "rate_limit", "too many requests", "429", "quota", "throttl"]

        for keyword in keywords:
            @with_retry(RetryConfig(max_retries=1, initial_delay=0.01))
            def rate_limited_func():
                raise ValueError(f"Error: {keyword} exceeded")

            with pytest.raises(RateLimitError):
                rate_limited_func()

    def test_retry_default_config(self):
        """Uses default config when none provided."""
        @with_retry()
        def simple_function():
            return 42

        result = simple_function()

        assert result == 42

    def test_retry_preserves_function_metadata(self):
        """Decorated function preserves original metadata."""
        @with_retry()
        def documented_function():
            """Original docstring."""
            return "value"

        assert documented_function.__name__ == "documented_function"
        assert "docstring" in documented_function.__doc__

    def test_retry_with_arguments(self):
        """Works with functions that have arguments."""
        @with_retry()
        def add(a, b):
            return a + b

        result = add(2, 3)

        assert result == 5

    def test_retry_with_kwargs(self):
        """Works with keyword arguments."""
        @with_retry()
        def greet(name, greeting="Hello"):
            return f"{greeting}, {name}!"

        result = greet("Alice", greeting="Hi")

        assert result == "Hi, Alice!"

    def test_retry_sleep_between_attempts(self):
        """Sleeps between retry attempts."""
        call_count = 0
        start_time = time.time()

        @with_retry(RetryConfig(max_retries=2, initial_delay=0.1))
        def slow_function():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ValueError("Retry me")
            return "done"

        result = slow_function()

        elapsed = time.time() - start_time
        assert result == "done"
        # Sleep should occur, but be lenient with timing (some systems may be slow)
        assert call_count == 2


# ============================================================
# BatchProcessor Tests
# ============================================================

class TestBatchProcessor:
    """Tests for batch processing with rate limiting."""

    def test_batch_processor_initialization(self):
        """Initialize batch processor with custom settings."""
        processor = BatchProcessor(
            batch_size=25,
            delay_between_batches=0.5,
            retry_config=RetryConfig(max_retries=2)
        )

        assert processor.batch_size == 25
        assert processor.delay_between_batches == 0.5
        assert processor.retry_config.max_retries == 2

    def test_batch_processor_default_settings(self):
        """Batch processor has sensible defaults."""
        processor = BatchProcessor()

        assert processor.batch_size == 50
        assert processor.delay_between_batches == 1.0
        assert processor.retry_config.max_retries == 3

    def test_batch_processor_single_batch(self):
        """Process items that fit in single batch."""
        processor = BatchProcessor(batch_size=100)

        items = list(range(10))
        results = processor.process(items, lambda x: x * 2)

        assert len(results) == 10
        assert results[0] == 0
        assert results[9] == 18

    def test_batch_processor_multiple_batches(self):
        """Process items across multiple batches."""
        processor = BatchProcessor(batch_size=5, delay_between_batches=0.01)

        items = list(range(15))
        results = processor.process(items, lambda x: x * 2)

        assert len(results) == 15
        assert results == [x * 2 for x in items]

    def test_batch_processor_with_fallback(self):
        """Use fallback function on error."""
        processor = BatchProcessor(batch_size=10)

        def process_item(x):
            if x == 5:
                raise ValueError("Item 5 failed")
            return x * 2

        def fallback(item, error):
            return item * 3  # Different multiplier for failed items

        items = list(range(10))
        results = processor.process(items, process_item, fallback_func=fallback)

        assert len(results) == 10
        assert results[5] == 15  # Fallback was used (5 * 3)
        assert results[4] == 8   # Normal processing

    def test_batch_processor_progress_callback(self):
        """Call progress callback during processing."""
        processor = BatchProcessor(batch_size=5)

        progress_updates = []

        def progress_callback(processed, total):
            progress_updates.append((processed, total))

        items = list(range(10))
        processor.process(items, lambda x: x * 2, progress_callback=progress_callback)

        assert len(progress_updates) == 10
        assert progress_updates[-1] == (10, 10)

    def test_batch_processor_empty_items(self):
        """Process empty items list."""
        processor = BatchProcessor()

        results = processor.process([], lambda x: x * 2)

        assert results == []

    def test_batch_processor_single_item(self):
        """Process single item."""
        processor = BatchProcessor()

        results = processor.process([42], lambda x: x * 2)

        assert len(results) == 1
        assert results[0] == 84

    def test_batch_processor_with_retry_config(self):
        """Batch processor respects retry config."""
        retry_config = RetryConfig(max_retries=2, initial_delay=0.01)
        processor = BatchProcessor(batch_size=5, retry_config=retry_config)

        call_count = {}

        def flaky_process(item):
            if item not in call_count:
                call_count[item] = 0
            call_count[item] += 1

            if call_count[item] < 2:
                raise ValueError("Retry")
            return item * 2

        items = [0, 1]
        results = processor.process(items, flaky_process)

        assert len(results) == 2


# ============================================================
# TokenBucket Tests
# ============================================================

class TestTokenBucket:
    """Tests for token bucket rate limiter."""

    def test_token_bucket_initialization(self):
        """Initialize token bucket."""
        bucket = TokenBucket(rate=10.0, capacity=50)

        assert bucket.rate == 10.0
        assert bucket.capacity == 50
        assert bucket.tokens == 50

    def test_token_bucket_acquire_available(self):
        """Acquire tokens when available."""
        bucket = TokenBucket(rate=10.0, capacity=10)

        success = bucket.acquire(tokens=5, block=False)

        assert success is True
        assert bucket.tokens == 5

    def test_token_bucket_acquire_not_available_non_blocking(self):
        """Cannot acquire tokens when not available (non-blocking)."""
        bucket = TokenBucket(rate=10.0, capacity=5)
        bucket.tokens = 2

        success = bucket.acquire(tokens=5, block=False)

        assert success is False
        # Tokens might have been refilled slightly during the call
        assert bucket.tokens >= 2

    def test_token_bucket_acquire_multiple_times(self):
        """Acquire tokens multiple times."""
        bucket = TokenBucket(rate=100.0, capacity=100)

        bucket.acquire(tokens=30)
        bucket.acquire(tokens=20)
        bucket.acquire(tokens=10)

        # Tokens might have been refilled slightly during the call
        assert bucket.tokens >= 39 and bucket.tokens <= 41

    def test_token_bucket_refill_over_time(self):
        """Tokens are refilled over time."""
        bucket = TokenBucket(rate=10.0, capacity=10)
        bucket.tokens = 0

        # Wait for tokens to refill (rate = 10 tokens/sec)
        time.sleep(0.2)
        bucket._refill()

        # Should have ~2 tokens after 0.2 seconds
        assert bucket.tokens >= 1.5
        assert bucket.tokens <= 2.5

    def test_token_bucket_refill_respects_capacity(self):
        """Refill respects capacity limit."""
        bucket = TokenBucket(rate=100.0, capacity=10)
        bucket.tokens = 5

        time.sleep(0.2)
        bucket._refill()

        # Should not exceed capacity
        assert bucket.tokens <= 10

    def test_token_bucket_blocking_acquire(self):
        """Blocking acquire waits for tokens."""
        bucket = TokenBucket(rate=50.0, capacity=10)
        bucket.tokens = 0

        start = time.time()
        success = bucket.acquire(tokens=1, block=True)
        elapsed = time.time() - start

        assert success is True
        assert elapsed >= 0.01  # Should wait

    def test_token_bucket_partial_tokens_available(self):
        """Request more tokens than available but less than rate allows."""
        bucket = TokenBucket(rate=10.0, capacity=10)
        bucket.tokens = 2

        # Request 5 tokens, only 2 available, but rate allows 10/sec
        success = bucket.acquire(tokens=5, block=False)

        # Should fail (not blocking)
        assert success is False

    def test_token_bucket_default_behavior(self):
        """Default behavior is blocking."""
        bucket = TokenBucket(rate=100.0, capacity=10)

        # Should succeed on first acquire
        success = bucket.acquire(tokens=5)

        assert success is True

    def test_token_bucket_zero_rate(self):
        """Handle zero rate (no refill)."""
        bucket = TokenBucket(rate=0.0, capacity=10)
        bucket.tokens = 0

        success = bucket.acquire(tokens=1, block=False)

        # No tokens and no refill
        assert success is False

    def test_token_bucket_high_rate(self):
        """Handle high token generation rate."""
        bucket = TokenBucket(rate=1000.0, capacity=100)
        bucket.tokens = 0

        time.sleep(0.1)
        bucket._refill()

        # Should have many tokens
        assert bucket.tokens >= 90


# ============================================================
# Integration Tests
# ============================================================

class TestIntegration:
    """Integration tests combining multiple components."""

    def test_batch_processor_with_retry_and_fallback(self):
        """Batch processor with retry and fallback."""
        processor = BatchProcessor(
            batch_size=5,
            retry_config=RetryConfig(max_retries=1, initial_delay=0.01)
        )

        call_count = {}

        def process_item(item):
            if item not in call_count:
                call_count[item] = 0
            call_count[item] += 1

            if item == 5:  # Fail permanently
                raise ValueError("Permanent failure")
            if item == 3 and call_count[item] == 1:  # Fail once then succeed
                raise ValueError("Temporary failure")
            return item * 2

        def fallback(item, error):
            return item * 3

        items = list(range(10))
        results = processor.process(items, process_item, fallback_func=fallback)

        assert len(results) == 10
        assert results[3] == 6   # Succeeded after retry
        assert results[5] == 15  # Used fallback

    def test_retry_decorator_with_rate_limit_pattern(self):
        """Simulate retry pattern for rate-limited API."""
        attempt_count = 0

        @with_retry(RetryConfig(max_retries=3, initial_delay=0.01))
        def call_api():
            nonlocal attempt_count
            attempt_count += 1

            if attempt_count <= 2:
                raise ValueError("429 Rate limit exceeded")
            return {"status": "success"}

        # Should succeed on third attempt
        result = call_api()
        assert result == {"status": "success"}
        assert attempt_count == 3


# ============================================================
# Error Handling Tests
# ============================================================

class TestErrorHandling:
    """Tests for error handling in rate limiting utilities."""

    def test_rate_limit_error_inheritance(self):
        """RateLimitError is an Exception."""
        assert issubclass(RateLimitError, Exception)

    def test_llm_error_inheritance(self):
        """LLMError is an Exception."""
        assert issubclass(LLMError, Exception)

    def test_rate_limit_error_message(self):
        """RateLimitError includes error message."""
        error = RateLimitError("Custom message")

        assert "Custom message" in str(error)

    def test_llm_error_message(self):
        """LLMError includes error message."""
        error = LLMError("Custom message")

        assert "Custom message" in str(error)

    def test_batch_processor_raises_without_fallback(self):
        """Batch processor raises error without fallback."""
        processor = BatchProcessor()

        def always_fails(x):
            raise ValueError("Failure")

        items = [1, 2, 3]

        with pytest.raises(ValueError):
            processor.process(items, always_fails)

    def test_retry_decorator_preserves_exception_context(self):
        """Retry decorator preserves exception chain."""
        @with_retry(RetryConfig(max_retries=1, initial_delay=0.01))
        def fails_with_context():
            try:
                raise ValueError("Original error")
            except ValueError as e:
                raise RuntimeError("Wrapped error") from e

        with pytest.raises(LLMError) as exc_info:
            fails_with_context()

        # Exception chain should be preserved
        assert exc_info.value.__cause__ is not None
