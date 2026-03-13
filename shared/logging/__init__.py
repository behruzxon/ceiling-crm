"""
shared.logging
~~~~~~~~~~~~~~
Structured JSON logging via structlog.
Call configure_logging() once at application startup.
"""

from shared.logging.setup import (
    bind_request_context,
    clear_request_context,
    configure_logging,
    get_logger,
)

__all__ = [
    "bind_request_context",
    "clear_request_context",
    "configure_logging",
    "get_logger",
]
