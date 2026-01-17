"""Configuration dataclasses for resilience patterns.

This module defines configuration objects for retry logic, circuit breakers,
and other resilience mechanisms.
"""
import os
from dataclasses import dataclass


@dataclass
class RetryConfig:
    """Configuration for retry behavior with exponential backoff.

    Attributes:
        max_attempts: Maximum number of retry attempts (default: 3)
        base_delay: Initial delay between retries in seconds (default: 1.0)
        max_delay: Maximum delay between retries in seconds (default: 60.0)
        exponential_base: Base for exponential backoff calculation (default: 2.0)
        rate_limit_delay: Special delay for rate limit (429) errors (default: 30.0)
        jitter: Whether to add random jitter to delays (default: True)
    """
    max_attempts: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    exponential_base: float = 2.0
    rate_limit_delay: float = 30.0
    jitter: bool = True

    @classmethod
    def from_env(cls) -> "RetryConfig":
        """Create RetryConfig from environment variables.

        Environment variables:
            RESILIENCE_RETRY_MAX_ATTEMPTS: Max retry attempts (default: 3)
            RESILIENCE_RETRY_BASE_DELAY: Initial delay in seconds (default: 1.0)
            RESILIENCE_RETRY_MAX_DELAY: Maximum delay in seconds (default: 60.0)
            RESILIENCE_RETRY_RATE_LIMIT_DELAY: Rate limit delay (default: 30.0)

        Returns:
            RetryConfig instance with values from environment or defaults
        """
        return cls(
            max_attempts=int(os.getenv("RESILIENCE_RETRY_MAX_ATTEMPTS", "3")),
            base_delay=float(os.getenv("RESILIENCE_RETRY_BASE_DELAY", "1.0")),
            max_delay=float(os.getenv("RESILIENCE_RETRY_MAX_DELAY", "60.0")),
            rate_limit_delay=float(os.getenv("RESILIENCE_RETRY_RATE_LIMIT_DELAY", "30.0")),
        )


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker behavior.

    The circuit breaker prevents repeated failures by temporarily disabling
    sources that have exceeded failure thresholds.

    States:
        - CLOSED: Normal operation, requests pass through
        - OPEN: Circuit tripped, requests are blocked until recovery_timeout
        - HALF-OPEN: After recovery_timeout, allow one request to test recovery

    Attributes:
        failure_threshold: Number of consecutive failures to open circuit (default: 5)
        recovery_timeout: Seconds to wait before attempting recovery (default: 300)
        half_open_max_calls: Max calls allowed in half-open state (default: 1)
    """
    failure_threshold: int = 5
    recovery_timeout: int = 300  # 5 minutes
    half_open_max_calls: int = 1

    @classmethod
    def from_env(cls) -> "CircuitBreakerConfig":
        """Create CircuitBreakerConfig from environment variables.

        Environment variables:
            RESILIENCE_CB_FAILURE_THRESHOLD: Failures to open circuit (default: 5)
            RESILIENCE_CB_RECOVERY_TIMEOUT: Recovery timeout in seconds (default: 300)

        Returns:
            CircuitBreakerConfig instance with values from environment or defaults
        """
        return cls(
            failure_threshold=int(os.getenv("RESILIENCE_CB_FAILURE_THRESHOLD", "5")),
            recovery_timeout=int(os.getenv("RESILIENCE_CB_RECOVERY_TIMEOUT", "300")),
        )


@dataclass
class ValidationConfig:
    """Configuration for source validation behavior.

    Attributes:
        default_timeout: Default timeout for test fetch operations (default: 10)
        max_url_length: Maximum allowed URL length (default: 2048)
        require_https: Whether to require HTTPS URLs (default: False)
    """
    default_timeout: int = 10
    max_url_length: int = 2048
    require_https: bool = False

    @classmethod
    def from_env(cls) -> "ValidationConfig":
        """Create ValidationConfig from environment variables.

        Environment variables:
            RESILIENCE_VALIDATION_TIMEOUT: Default validation timeout (default: 10)
            RESILIENCE_VALIDATION_MAX_URL_LENGTH: Max URL length (default: 2048)
            RESILIENCE_VALIDATION_REQUIRE_HTTPS: Require HTTPS (default: false)

        Returns:
            ValidationConfig instance with values from environment or defaults
        """
        return cls(
            default_timeout=int(os.getenv("RESILIENCE_VALIDATION_TIMEOUT", "10")),
            max_url_length=int(os.getenv("RESILIENCE_VALIDATION_MAX_URL_LENGTH", "2048")),
            require_https=os.getenv("RESILIENCE_VALIDATION_REQUIRE_HTTPS", "").lower() == "true",
        )
