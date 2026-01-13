"""Structured logging configuration using structlog.

This module provides industry-standard structured JSON logging with automatic
context propagation via contextvars. The design is forward-compatible with
OpenTelemetry for the enterprise multi-user version.

Usage:
    from reconly_core.logging import configure_logging, generate_trace_id, get_trace_id, get_logger

    # At application startup
    configure_logging()

    # At the start of a feed run
    trace_id = generate_trace_id()

    # Get a logger with automatic trace_id binding
    logger = get_logger(__name__)
    logger.info("Processing feed", feed_id=123)
"""

import io
import logging
import sys
import uuid
from contextvars import ContextVar
from typing import Optional

import structlog
from structlog.types import Processor


_utf8_configured = False

def _ensure_utf8_stdout() -> None:
    """Ensure stdout uses UTF-8 encoding on Windows.

    On Windows, the default console encoding (cp1252) cannot handle
    many Unicode characters, causing UnicodeEncodeError when logging
    content with special characters (e.g., German umlauts, emojis).

    Note: This function only runs once to avoid conflicts with pytest's
    capture system which also manages stdout/stderr.
    """
    global _utf8_configured
    if _utf8_configured:
        return

    if sys.platform == 'win32' and hasattr(sys.stdout, 'buffer'):
        # Only wrap if not already UTF-8 encoded
        if getattr(sys.stdout, 'encoding', '').lower() != 'utf-8':
            # Reconfigure stdout to use UTF-8 with error replacement
            sys.stdout = io.TextIOWrapper(
                sys.stdout.buffer,
                encoding='utf-8',
                errors='replace',
                line_buffering=True
            )
        if getattr(sys.stderr, 'encoding', '').lower() != 'utf-8':
            sys.stderr = io.TextIOWrapper(
                sys.stderr.buffer,
                encoding='utf-8',
                errors='replace',
                line_buffering=True
            )

    _utf8_configured = True


# ContextVar for trace ID propagation across async boundaries
trace_id_var: ContextVar[Optional[str]] = ContextVar("trace_id", default=None)


def generate_trace_id() -> str:
    """Generate a new trace ID and store it in the context.

    Returns:
        The generated trace ID (UUID4 string)
    """
    trace_id = str(uuid.uuid4())
    trace_id_var.set(trace_id)
    return trace_id


def get_trace_id() -> Optional[str]:
    """Get the current trace ID from the context.

    Returns:
        The current trace ID, or None if not set
    """
    return trace_id_var.get()


def clear_trace_id() -> None:
    """Clear the current trace ID from the context."""
    trace_id_var.set(None)


def _add_trace_id(logger: logging.Logger, method_name: str, event_dict: dict) -> dict:
    """Structlog processor to add trace_id to log events."""
    trace_id = trace_id_var.get()
    if trace_id:
        event_dict["trace_id"] = trace_id
    return event_dict


def configure_logging(
    log_level: str = "INFO",
    json_output: bool = False,
    development: bool = True,
) -> None:
    """Configure structured logging for the application.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        json_output: If True, output logs as JSON (good for production/log aggregation)
        development: If True, use colored console output (good for local development)
    """
    # Ensure UTF-8 output on Windows to prevent encoding errors
    _ensure_utf8_stdout()

    # Shared processors for all configurations
    # Note: We skip add_logger_name as PrintLoggerFactory doesn't support it
    shared_processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        _add_trace_id,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
    ]

    if json_output:
        # Production: JSON output for log aggregation
        shared_processors.append(structlog.processors.JSONRenderer())
    elif development:
        # Development: colored console output
        shared_processors.append(structlog.dev.ConsoleRenderer(colors=True))
    else:
        # Plain text output
        shared_processors.append(structlog.processors.KeyValueRenderer())

    # Configure structlog
    structlog.configure(
        processors=shared_processors,
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, log_level.upper())
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Also configure standard library logging to work with structlog
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, log_level.upper()),
    )


def get_logger(name: str) -> structlog.BoundLogger:
    """Get a structlog logger instance.

    Args:
        name: Logger name (typically __name__)

    Returns:
        A bound structlog logger
    """
    return structlog.get_logger(name)


# Convenience exports
__all__ = [
    "configure_logging",
    "generate_trace_id",
    "get_trace_id",
    "clear_trace_id",
    "get_logger",
    "trace_id_var",
]
