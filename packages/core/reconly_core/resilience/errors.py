"""Error types and classification for resilience patterns.

This module defines error categories and a base exception class for
resilience-related errors throughout the platform.
"""
import re
from enum import Enum
from typing import Any, Dict, Optional, Union

import requests


class ErrorCategory(Enum):
    """Categories for classifying errors to determine retry behavior.

    Attributes:
        TRANSIENT: Temporary failures that may succeed on retry
                   (network timeout, 5xx errors, rate limits)
        PERMANENT: Failures that will not succeed on retry
                   (404, invalid URL, parse errors)
        CONFIGURATION: Missing or invalid configuration
                       (missing API key, invalid settings)
    """
    TRANSIENT = "transient"
    PERMANENT = "permanent"
    CONFIGURATION = "configuration"


class ResilienceError(Exception):
    """Base exception for resilience-related errors.

    Attributes:
        message: Human-readable error message
        category: Error category for retry/fallback decisions
        source: Original error or exception that caused this error
        context: Additional context about the error (e.g., source_id, provider)
    """

    def __init__(
        self,
        message: str,
        category: ErrorCategory = ErrorCategory.PERMANENT,
        source: Optional[BaseException] = None,
        context: Optional[Dict[str, Any]] = None,
    ):
        """Initialize a ResilienceError.

        Args:
            message: Human-readable error message
            category: Error category for retry/fallback decisions
            source: Original exception that caused this error
            context: Additional context about the error
        """
        super().__init__(message)
        self.message = message
        self.category = category
        self.source = source
        self.context = context or {}

    def __str__(self) -> str:
        """Return string representation of the error."""
        return f"[{self.category.value}] {self.message}"

    def __repr__(self) -> str:
        """Return detailed representation of the error."""
        return (
            f"ResilienceError(message={self.message!r}, "
            f"category={self.category!r}, "
            f"context={self.context!r})"
        )

    @property
    def is_retryable(self) -> bool:
        """Check if this error category supports retry.

        Returns:
            True if the error is transient and may succeed on retry
        """
        return self.category == ErrorCategory.TRANSIENT


class ValidationError(ResilienceError):
    """Error raised during source validation.

    Always classified as PERMANENT since validation failures
    indicate configuration issues that won't be fixed by retry.
    """

    def __init__(
        self,
        message: str,
        source: Optional[BaseException] = None,
        context: Optional[Dict[str, Any]] = None,
    ):
        """Initialize a ValidationError.

        Args:
            message: Human-readable validation error message
            source: Original exception that caused this error
            context: Additional context (e.g., field name, invalid value)
        """
        super().__init__(
            message=message,
            category=ErrorCategory.PERMANENT,
            source=source,
            context=context,
        )


class CircuitOpenError(ResilienceError):
    """Error raised when attempting to use a source with open circuit.

    This indicates the source has exceeded failure thresholds and
    is temporarily disabled for recovery.
    """

    def __init__(
        self,
        message: str,
        recovery_at: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ):
        """Initialize a CircuitOpenError.

        Args:
            message: Human-readable error message
            recovery_at: ISO timestamp when circuit will attempt recovery
            context: Additional context (e.g., source_id, failure_count)
        """
        ctx = context or {}
        if recovery_at:
            ctx["recovery_at"] = recovery_at
        super().__init__(
            message=message,
            category=ErrorCategory.TRANSIENT,
            context=ctx,
        )


def classify_error(error: Union[Exception, int, str]) -> ErrorCategory:
    """Classify an error to determine retry behavior.

    This function analyzes errors from various sources (HTTP status codes,
    exception types, error messages) and categorizes them to determine
    whether the operation should be retried, marked as permanently failed,
    or flagged as a configuration issue.

    Args:
        error: The error to classify. Can be:
            - An Exception object (e.g., requests.Timeout, ValueError)
            - An HTTP status code (int)
            - An error message string

    Returns:
        ErrorCategory indicating how to handle the error:
            - TRANSIENT: Retry with backoff (timeout, 5xx, 429, connection errors)
            - PERMANENT: Do not retry (4xx except 429, parse errors)
            - CONFIGURATION: Fix config before retry (missing/invalid API key)

    Examples:
        >>> classify_error(requests.Timeout())
        ErrorCategory.TRANSIENT

        >>> classify_error(404)
        ErrorCategory.PERMANENT

        >>> classify_error(429)
        ErrorCategory.TRANSIENT

        >>> classify_error("Missing API key")
        ErrorCategory.CONFIGURATION
    """
    # Handle HTTP status codes directly
    if isinstance(error, int):
        return _classify_http_status(error)

    # Handle exception objects
    if isinstance(error, Exception):
        return _classify_exception(error)

    # Handle error message strings
    if isinstance(error, str):
        return _classify_error_message(error)

    # Default to permanent for unknown types
    return ErrorCategory.PERMANENT


def _classify_http_status(status_code: int) -> ErrorCategory:
    """Classify an HTTP status code.

    Args:
        status_code: HTTP status code

    Returns:
        ErrorCategory based on the status code
    """
    # Rate limit - transient, but needs special handling
    if status_code == 429:
        return ErrorCategory.TRANSIENT

    # Server errors (5xx) - transient
    if 500 <= status_code < 600:
        return ErrorCategory.TRANSIENT

    # Authentication errors - configuration
    if status_code in (401, 403):
        return ErrorCategory.CONFIGURATION

    # Other client errors (4xx) - permanent
    if 400 <= status_code < 500:
        return ErrorCategory.PERMANENT

    # Success codes shouldn't reach here, but treat as permanent
    return ErrorCategory.PERMANENT


def _classify_exception(error: Exception) -> ErrorCategory:
    """Classify an exception object.

    Args:
        error: The exception to classify

    Returns:
        ErrorCategory based on exception type and content
    """
    error_type = type(error).__name__
    error_msg = str(error).lower()

    # Timeout errors - transient
    if isinstance(error, (requests.Timeout,)):
        return ErrorCategory.TRANSIENT
    if "timeout" in error_type.lower() or "timeout" in error_msg:
        return ErrorCategory.TRANSIENT

    # Connection errors - transient
    if isinstance(error, (requests.ConnectionError, ConnectionError, OSError)):
        return ErrorCategory.TRANSIENT

    if "connection" in error_type.lower():
        return ErrorCategory.TRANSIENT

    # Check error message for connection-related keywords
    if "connection" in error_msg or "network" in error_msg:
        return ErrorCategory.TRANSIENT

    # Rate limit errors - transient
    if "rate" in error_msg and ("limit" in error_msg or "exceeded" in error_msg):
        return ErrorCategory.TRANSIENT
    if "429" in error_msg or "too many requests" in error_msg:
        return ErrorCategory.TRANSIENT

    # Server errors (5xx) - transient
    if _contains_5xx_error(error_msg):
        return ErrorCategory.TRANSIENT
    if "internal server error" in error_msg or "service unavailable" in error_msg:
        return ErrorCategory.TRANSIENT
    if "bad gateway" in error_msg or "gateway timeout" in error_msg:
        return ErrorCategory.TRANSIENT

    # Temporary/transient indicators
    if "temporary" in error_msg or "transient" in error_msg:
        return ErrorCategory.TRANSIENT
    if "try again" in error_msg or "retry" in error_msg:
        return ErrorCategory.TRANSIENT

    # Configuration errors
    if _is_configuration_error(error_msg):
        return ErrorCategory.CONFIGURATION

    # Authentication errors - often configuration
    if "authentication" in error_msg or "unauthorized" in error_msg:
        return ErrorCategory.CONFIGURATION
    if "api_key" in error_msg or "api key" in error_msg:
        return ErrorCategory.CONFIGURATION
    if "invalid key" in error_msg or "invalid token" in error_msg:
        return ErrorCategory.CONFIGURATION
    if "401" in error_msg or "403" in error_msg:
        return ErrorCategory.CONFIGURATION

    # Parse/validation errors - permanent
    if isinstance(error, (ValueError, TypeError, KeyError)):
        # Check if it might be config-related
        if _is_configuration_error(error_msg):
            return ErrorCategory.CONFIGURATION
        return ErrorCategory.PERMANENT

    # JSON decode errors - permanent
    if "json" in error_type.lower() or "decode" in error_msg:
        return ErrorCategory.PERMANENT

    # Not found errors - permanent
    if "404" in error_msg or "not found" in error_msg:
        return ErrorCategory.PERMANENT

    # Model not found - configuration (user needs to change model)
    if "model" in error_msg and ("not found" in error_msg or "does not exist" in error_msg):
        return ErrorCategory.CONFIGURATION

    # Default: treat as permanent to avoid infinite retries
    return ErrorCategory.PERMANENT


def _classify_error_message(message: str) -> ErrorCategory:
    """Classify an error based on its message string.

    Args:
        message: Error message string

    Returns:
        ErrorCategory based on message content
    """
    msg_lower = message.lower()

    # Transient patterns
    transient_patterns = [
        "timeout", "timed out",
        "connection", "network",
        "rate limit", "rate_limit", "429", "too many requests",
        "503", "502", "500", "504",
        "service unavailable", "internal server error",
        "bad gateway", "gateway timeout",
        "temporary", "transient", "try again", "retry",
    ]
    for pattern in transient_patterns:
        if pattern in msg_lower:
            return ErrorCategory.TRANSIENT

    # Configuration patterns
    config_patterns = [
        "api key", "api_key", "apikey",
        "missing key", "invalid key",
        "authentication", "unauthorized", "401", "403",
        "invalid token", "missing token",
        "invalid model", "model not found",
        "configuration", "not configured",
    ]
    for pattern in config_patterns:
        if pattern in msg_lower:
            return ErrorCategory.CONFIGURATION

    # Default to permanent
    return ErrorCategory.PERMANENT


def _contains_5xx_error(message: str) -> bool:
    """Check if message contains a 5xx HTTP status code.

    Args:
        message: Error message to check

    Returns:
        True if message contains a 5xx status code
    """
    # Look for patterns like "500", "502", "503", "504", etc.
    return bool(re.search(r"\b5\d{2}\b", message))


def _is_configuration_error(message: str) -> bool:
    """Check if error message indicates a configuration problem.

    Args:
        message: Error message to check

    Returns:
        True if the error appears to be configuration-related
    """
    config_indicators = [
        "missing", "not set", "not found", "required",
        "invalid", "configuration", "config",
    ]
    key_indicators = [
        "api key", "api_key", "apikey", "token", "credential",
    ]

    msg_lower = message.lower()

    # Check for explicit configuration errors
    for config in config_indicators:
        for key in key_indicators:
            if config in msg_lower and key in msg_lower:
                return True

    return False


def is_rate_limit_error(error: Union[Exception, int, str]) -> bool:
    """Check if an error is specifically a rate limit (429) error.

    This is useful for applying special handling like longer delays
    for rate-limited requests.

    Args:
        error: The error to check

    Returns:
        True if this is a rate limit error
    """
    if isinstance(error, int):
        return error == 429

    error_msg = str(error).lower()
    return (
        "429" in error_msg
        or "rate limit" in error_msg
        or "rate_limit" in error_msg
        or "too many requests" in error_msg
    )
