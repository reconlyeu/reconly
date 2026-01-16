"""Resilience module for platform-wide error handling and recovery patterns.

This module provides:
- Error classification for retry/fallback decisions
- Configuration for retry and circuit breaker behavior
- Retry logic with exponential backoff
- Source validation utilities
- Circuit breaker for source health management

Public API:
    ErrorCategory: Enum for classifying error types (TRANSIENT, PERMANENT, CONFIGURATION)
    ResilienceError: Base exception class with error category support
    ValidationError: Exception for validation failures
    CircuitOpenError: Exception when circuit breaker is open

    classify_error: Function to classify errors for retry decisions
    is_rate_limit_error: Function to check if error is a rate limit (429)

    RetryConfig: Configuration for retry behavior with exponential backoff
    CircuitBreakerConfig: Configuration for circuit breaker thresholds
    ValidationConfig: Configuration for source validation

    with_retry: Decorator for adding retry logic with exponential backoff
    calculate_delay: Function to calculate retry delay with jitter
    retry_with_result: Function for retry with detailed metadata

    SourceCircuitBreaker: Circuit breaker for managing source health

Example:
    >>> from reconly_core.resilience import (
    ...     ErrorCategory,
    ...     ResilienceError,
    ...     RetryConfig,
    ...     CircuitBreakerConfig,
    ...     SourceCircuitBreaker,
    ...     classify_error,
    ...     with_retry,
    ... )
    >>>
    >>> # Create retry config from environment
    >>> retry_config = RetryConfig.from_env()
    >>>
    >>> # Use retry decorator for transient error handling
    >>> @with_retry(retry_config)
    >>> def call_api():
    ...     return requests.get("https://api.example.com")
    >>>
    >>> # Classify an error to determine retry behavior
    >>> error = Exception("Connection timeout")
    >>> category = classify_error(error)
    >>> if category == ErrorCategory.TRANSIENT:
    ...     print("This error can be retried")
    >>>
    >>> # Create circuit breaker config with custom values
    >>> cb_config = CircuitBreakerConfig(
    ...     failure_threshold=3,
    ...     recovery_timeout=60,
    ... )
    >>>
    >>> # Use circuit breaker to manage source health
    >>> circuit_breaker = SourceCircuitBreaker(cb_config)
    >>> skip, reason = circuit_breaker.should_skip(source)
    >>> if skip:
    ...     print(f"Skipping source: {reason}")
    >>>
    >>> # Raise a transient error that can be retried
    >>> raise ResilienceError(
    ...     "Connection timeout",
    ...     category=ErrorCategory.TRANSIENT,
    ... )
"""
from reconly_core.resilience.errors import (
    CircuitOpenError,
    ErrorCategory,
    ResilienceError,
    ValidationError,
    classify_error,
    is_rate_limit_error,
)
from reconly_core.resilience.config import (
    CircuitBreakerConfig,
    RetryConfig,
    ValidationConfig,
)
from reconly_core.resilience.retry import (
    calculate_delay,
    retry_with_result,
    with_retry,
)
from reconly_core.resilience.circuit_breaker import SourceCircuitBreaker

__all__ = [
    # Error types
    "ErrorCategory",
    "ResilienceError",
    "ValidationError",
    "CircuitOpenError",
    # Error classification
    "classify_error",
    "is_rate_limit_error",
    # Configuration
    "RetryConfig",
    "CircuitBreakerConfig",
    "ValidationConfig",
    # Retry utilities
    "with_retry",
    "calculate_delay",
    "retry_with_result",
    # Circuit breaker
    "SourceCircuitBreaker",
]
