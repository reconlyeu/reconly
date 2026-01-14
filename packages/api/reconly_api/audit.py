"""Audit logging for security-relevant events.

This module provides structured audit logging for security events such as
authentication attempts, rate limiting, and configuration changes. Audit logs
are separate from application logs and can be used for security monitoring
and compliance.

Usage:
    from reconly_api.audit import audit_log, AuditEventType

    # Log a successful authentication
    audit_log(AuditEventType.AUTH_SUCCESS, ip="192.168.1.1")

    # Log a failed authentication
    audit_log(AuditEventType.AUTH_FAILURE, ip="192.168.1.1", details={"reason": "invalid_password"})
"""
from enum import Enum
from typing import Optional

from reconly_core.logging import get_logger


class AuditEventType(str, Enum):
    """Types of security audit events.

    Each event type represents a security-relevant action that should be logged
    for monitoring and compliance purposes.
    """

    # Authentication events
    AUTH_SUCCESS = "auth.success"
    AUTH_FAILURE = "auth.failure"

    # Rate limiting events
    RATE_LIMITED = "rate.limited"

    # Configuration events
    CONFIG_CHANGED = "config.changed"

    # Security events
    SECRET_KEY_INVALID = "security.secret_key_invalid"
    UNAUTHORIZED_ACCESS = "security.unauthorized_access"


def audit_log(
    event_type: AuditEventType,
    ip: Optional[str] = None,
    user_id: Optional[str] = None,
    details: Optional[dict] = None,
) -> None:
    """Log a security audit event with structured fields.

    This function logs security-relevant events in a structured format suitable
    for security monitoring and compliance. The logs are emitted at INFO level
    and include consistent fields for easy filtering and analysis.

    SECURITY NOTE: This function NEVER logs passwords, tokens, API keys, or
    other secrets. The 'details' dict should not contain sensitive information.

    Args:
        event_type: The type of audit event (from AuditEventType enum)
        ip: The client IP address associated with the event
        user_id: The user identifier (if applicable and known)
        details: Additional context about the event (never include secrets)

    Example:
        >>> audit_log(
        ...     AuditEventType.AUTH_FAILURE,
        ...     ip="192.168.1.1",
        ...     details={"reason": "invalid_password", "attempts": 3}
        ... )
    """
    logger = get_logger("audit")

    # Build the log context - only include non-None values
    log_context = {
        "audit_event": event_type.value,
    }

    if ip is not None:
        log_context["client_ip"] = ip

    if user_id is not None:
        log_context["user_id"] = user_id

    if details is not None:
        # Merge details into context, but prefix with 'audit_' to avoid collisions
        for key, value in details.items():
            log_context[f"audit_{key}"] = value

    # Log the audit event
    logger.info(
        f"Audit: {event_type.value}",
        **log_context,
    )


# Convenience exports
__all__ = [
    "AuditEventType",
    "audit_log",
]
