"""Circuit breaker implementation for source health management.

This module provides the SourceCircuitBreaker class for managing source health
and implementing the circuit breaker pattern to prevent repeated failures from
cascading through the system.

Circuit breaker states:
- CLOSED: Normal operation, requests pass through
- OPEN: Circuit tripped (too many failures), requests blocked until recovery_timeout
- HALF-OPEN: After recovery_timeout, allow one request to test if source recovered

Health status transitions:
- healthy: 0-2 consecutive failures
- degraded: 3-4 consecutive failures (warning state)
- unhealthy: 5+ consecutive failures, circuit is open
"""
from datetime import datetime
from typing import Optional, Tuple

from sqlalchemy.orm import Session

from reconly_core.database.models import Source
from reconly_core.resilience.config import CircuitBreakerConfig
from reconly_core.logging import get_logger


logger = get_logger(__name__)


class SourceCircuitBreaker:
    """Manages circuit breaker logic for source health.

    The circuit breaker prevents repeated failures by temporarily disabling
    sources that have exceeded failure thresholds. It tracks health status
    and provides methods to check if a source should be skipped.

    Example:
        >>> circuit_breaker = SourceCircuitBreaker()
        >>> skip, reason = circuit_breaker.should_skip(source)
        >>> if skip:
        ...     print(f"Skipping source: {reason}")
        >>> else:
        ...     # Process source
        ...     try:
        ...         fetch_source(source)
        ...         circuit_breaker.record_success(source, session)
        ...     except Exception as e:
        ...         circuit_breaker.record_failure(source, session, e)
    """

    def __init__(self, config: Optional[CircuitBreakerConfig] = None):
        """Initialize the circuit breaker.

        Args:
            config: Circuit breaker configuration. If None, loads from environment.
        """
        self.config = config or CircuitBreakerConfig.from_env()

    def should_skip(self, source: Source) -> Tuple[bool, str]:
        """Check if a source should be skipped due to circuit breaker state.

        This method checks:
        1. If the circuit is currently open (too many consecutive failures)
        2. If recovery timeout has passed (half-open state allows one attempt)

        Args:
            source: The source to check

        Returns:
            Tuple of (should_skip: bool, reason: str)
            - (False, "") if source can be processed
            - (True, reason) if source should be skipped with explanation
        """
        # Check if circuit is open
        if source.is_circuit_open:
            recovery_at = source.circuit_open_until.isoformat() if source.circuit_open_until else "unknown"
            reason = (
                f"Circuit open for source '{source.name}' "
                f"({source.consecutive_failures} consecutive failures). "
                f"Recovery at: {recovery_at}"
            )
            logger.info(
                "circuit_breaker_skip",
                source_id=source.id,
                source_name=source.name,
                consecutive_failures=source.consecutive_failures,
                health_status=source.health_status,
                circuit_open_until=recovery_at,
            )
            return True, reason

        # Check if we're in half-open state (recovery timeout just passed)
        # This allows one request through to test if source has recovered
        if source.health_status == 'unhealthy' and not source.is_circuit_open:
            logger.info(
                "circuit_breaker_half_open",
                source_id=source.id,
                source_name=source.name,
                consecutive_failures=source.consecutive_failures,
                message="Attempting recovery test (half-open state)",
            )
            # Allow the request through for recovery testing
            return False, ""

        # Source is healthy or degraded - allow request
        if source.health_status == 'degraded':
            logger.warning(
                "circuit_breaker_degraded",
                source_id=source.id,
                source_name=source.name,
                consecutive_failures=source.consecutive_failures,
                message="Source is degraded but still processing",
            )

        return False, ""

    def record_success(self, source: Source, session: Session) -> None:
        """Record a successful fetch for a source.

        Updates the source's health status to indicate success:
        - Resets consecutive failures to 0
        - Updates last_success_at timestamp
        - Sets health_status to 'healthy'
        - Clears circuit_open_until

        Args:
            source: The source that succeeded
            session: Database session for committing changes
        """
        previous_status = source.health_status
        previous_failures = source.consecutive_failures

        source.update_health_success()

        logger.info(
            "circuit_breaker_success",
            source_id=source.id,
            source_name=source.name,
            previous_status=previous_status,
            previous_failures=previous_failures,
            new_status=source.health_status,
        )

        # Log recovery event if source was previously unhealthy
        if previous_status == 'unhealthy':
            logger.info(
                "circuit_breaker_recovered",
                source_id=source.id,
                source_name=source.name,
                previous_failures=previous_failures,
                message="Source recovered from unhealthy state",
            )

        session.add(source)

    def record_failure(
        self,
        source: Source,
        session: Session,
        error: Optional[Exception] = None,
    ) -> None:
        """Record a failed fetch for a source.

        Updates the source's health status to indicate failure:
        - Increments consecutive_failures
        - Updates last_failure_at timestamp
        - Transitions health_status based on failure count
        - Opens circuit if threshold exceeded

        Args:
            source: The source that failed
            session: Database session for committing changes
            error: Optional exception that caused the failure
        """
        previous_status = source.health_status
        previous_failures = source.consecutive_failures

        source.update_health_failure(recovery_timeout=self.config.recovery_timeout)

        error_msg = str(error) if error else "Unknown error"

        logger.warning(
            "circuit_breaker_failure",
            source_id=source.id,
            source_name=source.name,
            previous_status=previous_status,
            previous_failures=previous_failures,
            new_status=source.health_status,
            new_failures=source.consecutive_failures,
            error=error_msg,
            threshold=self.config.failure_threshold,
        )

        # Log circuit opening event
        if source.health_status == 'unhealthy' and previous_status != 'unhealthy':
            logger.error(
                "circuit_breaker_opened",
                source_id=source.id,
                source_name=source.name,
                consecutive_failures=source.consecutive_failures,
                circuit_open_until=source.circuit_open_until.isoformat() if source.circuit_open_until else None,
                recovery_timeout=self.config.recovery_timeout,
                message=f"Circuit opened after {source.consecutive_failures} failures",
            )

        # Log degradation event
        if source.health_status == 'degraded' and previous_status == 'healthy':
            logger.warning(
                "circuit_breaker_degraded_transition",
                source_id=source.id,
                source_name=source.name,
                consecutive_failures=source.consecutive_failures,
                message="Source transitioned to degraded state",
            )

        session.add(source)

    def get_health_summary(self, source: Source) -> dict:
        """Get a summary of the source's health status.

        Args:
            source: The source to summarize

        Returns:
            Dictionary with health status details
        """
        def fmt_datetime(dt: Optional[datetime]) -> Optional[str]:
            return dt.isoformat() if dt else None

        return {
            "source_id": source.id,
            "source_name": source.name,
            "health_status": source.health_status,
            "consecutive_failures": source.consecutive_failures,
            "is_circuit_open": source.is_circuit_open,
            "circuit_open_until": fmt_datetime(source.circuit_open_until),
            "last_success_at": fmt_datetime(source.last_success_at),
            "last_failure_at": fmt_datetime(source.last_failure_at),
            "threshold": self.config.failure_threshold,
            "recovery_timeout": self.config.recovery_timeout,
        }
