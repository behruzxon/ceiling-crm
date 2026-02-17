"""
shared.logging
~~~~~~~~~~~~~~
Structured JSON logging via structlog.
Call configure_logging() once at application startup.
"""

from shared.logging.setup import configure_logging, get_logger

__all__ = ["configure_logging", "get_logger"]
