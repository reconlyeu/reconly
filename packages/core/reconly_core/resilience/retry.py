"""Retry logic with exponential backoff for resilient operations.

This module provides a retry decorator and utility functions for implementing
robust retry logic with exponential backoff, jitter, and special handling
for rate-limited requests.

Example:
    >>> from reconly_core.resilience.retry import with_retry
    >>> from reconly_core.resilience.config import RetryConfig
    >>>
    >>> config = RetryConfig(max_attempts=3, base_delay=1.0)
    >>>
    >>> @with_retry(config)
    >>> def fetch_data():
    ...     return requests.get("https://api.example.com/data")
"""
import asyncio
import functools
import random
import time
from typing import Callable, Optional, TypeVar, Any, Dict

import structlog

from reconly_core.resilience.config import RetryConfig
from reconly_core.resilience.errors import (
    ErrorCategory,
    classify_error,
    is_rate_limit_error,
)

logger = structlog.get_logger(__name__)

T = TypeVar("T")


def calculate_delay(
    attempt: int,
    config: RetryConfig,
    is_rate_limit: bool = False,
) -> float:
    """Calculate the delay before the next retry attempt.

    Uses exponential backoff with optional jitter and special handling
    for rate-limited requests.

    Args:
        attempt: Current attempt number (0-indexed)
        config: Retry configuration
        is_rate_limit: Whether this is a rate limit (429) error

    Returns:
        Delay in seconds before the next retry

    Example:
        >>> config = RetryConfig(base_delay=1.0, exponential_base=2.0)
        >>> calculate_delay(0, config)  # ~1.0 seconds
        >>> calculate_delay(1, config)  # ~2.0 seconds
        >>> calculate_delay(2, config)  # ~4.0 seconds
    """
    # Base exponential backoff: base_delay * (exponential_base ^ attempt)
    delay = config.base_delay * (config.exponential_base ** attempt)

    # Apply rate limit multiplier for 429 errors
    if is_rate_limit:
        delay = max(delay, config.rate_limit_delay)

    # Cap at max_delay
    delay = min(delay, config.max_delay)

    # Add jitter (random variation to prevent thundering herd)
    if config.jitter:
        # Add up to 10% random variation
        jitter_amount = delay * 0.1 * random.random()
        delay += jitter_amount

    return delay


def with_retry(
    config: Optional[RetryConfig] = None,
    classify_fn: Optional[Callable[[Exception], ErrorCategory]] = None,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Decorator that adds retry logic with exponential backoff.

    Wraps a function to automatically retry on transient failures with
    exponential backoff, jitter, and special rate-limit handling.

    Args:
        config: Retry configuration. If None, uses defaults from environment.
        classify_fn: Optional custom error classifier. If None, uses default classify_error().

    Returns:
        Decorated function with retry behavior

    Example:
        >>> @with_retry(RetryConfig(max_attempts=3))
        >>> def call_api():
        ...     response = requests.get("https://api.example.com")
        ...     response.raise_for_status()
        ...     return response.json()

    Note:
        - Only retries TRANSIENT errors (network issues, 5xx, 429)
        - PERMANENT and CONFIGURATION errors are raised immediately
        - Works with both sync and async functions
    """
    if config is None:
        config = RetryConfig.from_env()

    classifier = classify_fn or classify_error

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> T:
            return _retry_sync(func, args, kwargs, config, classifier)

        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> T:
            return await _retry_async(func, args, kwargs, config, classifier)

        # Return appropriate wrapper based on function type
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


def _handle_retry_error(
    error: Exception,
    func_name: str,
    attempt: int,
    config: RetryConfig,
    classifier: Callable[[Exception], ErrorCategory],
) -> tuple[float, dict]:
    """Handle error during retry and determine if should continue.

    Args:
        error: The exception that occurred
        func_name: Name of the function being retried
        attempt: Current attempt number (0-indexed)
        config: Retry configuration
        classifier: Error classification function

    Returns:
        Tuple of (delay_seconds, log_context) if should retry

    Raises:
        Exception: Re-raises the error if should not retry
    """
    category = classifier(error)
    is_rate_limit = is_rate_limit_error(error)

    log_context = {
        "function": func_name,
        "attempt": attempt + 1,
        "max_attempts": config.max_attempts,
        "error": str(error),
        "error_category": category.value,
        "is_rate_limit": is_rate_limit,
    }

    # Only retry TRANSIENT errors
    if category != ErrorCategory.TRANSIENT:
        logger.warning(
            "retry_not_attempted",
            reason="error_not_transient",
            **log_context,
        )
        raise error

    # Check if we have retries left
    if attempt >= config.max_attempts - 1:
        logger.error("retry_exhausted", **log_context)
        raise error

    # Calculate delay
    delay = calculate_delay(attempt, config, is_rate_limit)
    log_context["delay_seconds"] = round(delay, 2)

    logger.warning("retry_attempt", **log_context)

    return delay, log_context


def _log_retry_success(func_name: str, attempt: int, max_attempts: int) -> None:
    """Log successful retry after previous failures."""
    if attempt > 0:
        logger.info(
            "retry_succeeded",
            function=func_name,
            attempt=attempt + 1,
            total_attempts=max_attempts,
        )


def _retry_sync(
    func: Callable[..., T],
    args: tuple,
    kwargs: dict,
    config: RetryConfig,
    classifier: Callable[[Exception], ErrorCategory],
) -> T:
    """Execute a sync function with retry logic.

    Args:
        func: Function to execute
        args: Positional arguments
        kwargs: Keyword arguments
        config: Retry configuration
        classifier: Error classification function

    Returns:
        Function result on success

    Raises:
        Exception: The last error if all retries are exhausted
    """
    for attempt in range(config.max_attempts):
        try:
            result = func(*args, **kwargs)
            _log_retry_success(func.__name__, attempt, config.max_attempts)
            return result
        except Exception as e:
            delay, _ = _handle_retry_error(e, func.__name__, attempt, config, classifier)
            time.sleep(delay)

    raise RuntimeError("Unexpected retry loop exit")


async def _retry_async(
    func: Callable[..., T],
    args: tuple,
    kwargs: dict,
    config: RetryConfig,
    classifier: Callable[[Exception], ErrorCategory],
) -> T:
    """Execute an async function with retry logic.

    Args:
        func: Async function to execute
        args: Positional arguments
        kwargs: Keyword arguments
        config: Retry configuration
        classifier: Error classification function

    Returns:
        Function result on success

    Raises:
        Exception: The last error if all retries are exhausted
    """
    for attempt in range(config.max_attempts):
        try:
            result = await func(*args, **kwargs)
            _log_retry_success(func.__name__, attempt, config.max_attempts)
            return result
        except Exception as e:
            delay, _ = _handle_retry_error(e, func.__name__, attempt, config, classifier)
            await asyncio.sleep(delay)

    raise RuntimeError("Unexpected retry loop exit")


def retry_with_result(
    func: Callable[..., T],
    args: tuple = (),
    kwargs: Optional[dict] = None,
    config: Optional[RetryConfig] = None,
    classifier: Optional[Callable[[Exception], ErrorCategory]] = None,
) -> Dict[str, Any]:
    """Execute a function with retry and return detailed result metadata.

    Unlike with_retry decorator, this function returns a dict containing
    both the result and retry metadata useful for fallback chains.

    Args:
        func: Function to execute
        args: Positional arguments
        kwargs: Keyword arguments
        config: Retry configuration
        classifier: Error classification function

    Returns:
        Dictionary with:
            - 'success': bool indicating success
            - 'result': Function return value (if successful)
            - 'error': Exception (if failed)
            - 'error_category': ErrorCategory of final error
            - 'attempts': Number of attempts made
            - 'retry_delays': List of delay times used

    Example:
        >>> result = retry_with_result(call_api, (), {'timeout': 30})
        >>> if result['success']:
        ...     print(f"Got data after {result['attempts']} attempts")
        >>> else:
        ...     print(f"Failed: {result['error_category']}")
    """
    if config is None:
        config = RetryConfig.from_env()
    if kwargs is None:
        kwargs = {}

    classifier_fn = classifier or classify_error

    metadata: Dict[str, Any] = {
        "success": False,
        "result": None,
        "error": None,
        "error_category": None,
        "attempts": 0,
        "retry_delays": [],
    }

    for attempt in range(config.max_attempts):
        metadata["attempts"] = attempt + 1

        try:
            result = func(*args, **kwargs)
            metadata["success"] = True
            metadata["result"] = result
            return metadata

        except Exception as e:
            category = classifier_fn(e)
            metadata["error"] = e
            metadata["error_category"] = category

            log_context = {
                "function": func.__name__,
                "attempt": attempt + 1,
                "max_attempts": config.max_attempts,
                "error": str(e),
                "error_category": category.value,
            }

            # Only retry TRANSIENT errors
            if category != ErrorCategory.TRANSIENT:
                logger.warning(
                    "retry_not_attempted",
                    reason="error_not_transient",
                    **log_context,
                )
                return metadata

            # Check if we have retries left
            if attempt >= config.max_attempts - 1:
                logger.error(
                    "retry_exhausted",
                    **log_context,
                )
                return metadata

            # Calculate delay and sleep
            is_rate_limit = is_rate_limit_error(e)
            delay = calculate_delay(attempt, config, is_rate_limit)
            metadata["retry_delays"].append(delay)

            logger.warning(
                "retry_attempt",
                delay_seconds=round(delay, 2),
                is_rate_limit=is_rate_limit,
                **log_context,
            )

            time.sleep(delay)

    return metadata
