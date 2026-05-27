"""
shared.logging.setup
~~~~~~~~~~~~~~~~~~~~
Configures structlog for JSON structured logging output.

Features:
- JSON output in production (machine-parseable for Loki / CloudWatch)
- Human-readable colored output in development
- Automatic context injection: request_id, user_id, chat_id, update_id
- Standard library `logging` bridged through structlog
- Log level controlled by settings.log_level

Usage:
    from shared.logging import configure_logging, get_logger

    configure_logging()                    # call once at startup
    log = get_logger(__name__)
    log.info("lead_created", lead_id=42, category="led_podsvetka")
"""

from __future__ import annotations

import contextvars
import logging
import logging.config
import uuid
from typing import Any

import structlog
from structlog.types import EventDict, Processor

from shared.config import get_settings

# ─────────────────────────────────────────────────────────────────────────────
# Context variables for per-request tracing
# ─────────────────────────────────────────────────────────────────────────────

request_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "request_id", default=None
)
user_id_var: contextvars.ContextVar[int | None] = contextvars.ContextVar("user_id", default=None)


def bind_request_context(*, user_id: int | None = None) -> str:
    """Set request_id (uuid4) and optional user_id for current async context.

    Returns the generated request_id.
    """
    rid = uuid.uuid4().hex[:12]
    request_id_var.set(rid)
    if user_id is not None:
        user_id_var.set(user_id)
    return rid


def clear_request_context() -> None:
    """Reset context vars at end of request."""
    request_id_var.set(None)
    user_id_var.set(None)


# ─────────────────────────────────────────────────────────────────────────────
# Custom processors
# ─────────────────────────────────────────────────────────────────────────────


def drop_color_message_key(_logger: Any, _method: str, event_dict: EventDict) -> EventDict:
    """
    Remove the 'color_message' key injected by uvicorn.
    Keeps JSON output clean when running behind uvicorn.
    """
    event_dict.pop("color_message", None)
    return event_dict


def add_app_info(_logger: Any, _method: str, event_dict: EventDict) -> EventDict:
    """Inject static application metadata into every log record."""
    settings = get_settings()
    event_dict["app_env"] = settings.app_env
    return event_dict


def add_request_context(_logger: Any, _method: str, event_dict: EventDict) -> EventDict:
    """Inject per-request request_id and user_id from contextvars."""
    rid = request_id_var.get()
    if rid is not None:
        event_dict["request_id"] = rid
    uid = user_id_var.get()
    if uid is not None:
        event_dict["user_id"] = uid
    return event_dict


def rename_event_key(_logger: Any, _method: str, event_dict: EventDict) -> EventDict:
    """Rename 'event' to 'message' for ELK/Loki compatibility."""
    event_dict["message"] = event_dict.pop("event", "")
    return event_dict


# ─────────────────────────────────────────────────────────────────────────────
# Shared processor chain
# ─────────────────────────────────────────────────────────────────────────────


def _build_shared_processors(is_dev: bool) -> list[Processor]:
    """Build the shared processor chain, choosing the right exception formatter."""
    processors: list[Processor] = [
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.CallsiteParameterAdder(
            [
                structlog.processors.CallsiteParameter.FILENAME,
                structlog.processors.CallsiteParameter.FUNC_NAME,
                structlog.processors.CallsiteParameter.LINENO,
            ]
        ),
        add_app_info,
        add_request_context,
        drop_color_message_key,
    ]
    # In production, convert tracebacks to dicts for JSON serialisation.
    # In dev, omit — ConsoleRenderer handles exc_info natively.
    if not is_dev:
        processors.append(structlog.processors.dict_tracebacks)
    processors.append(structlog.processors.UnicodeDecoder())
    return processors


# ─────────────────────────────────────────────────────────────────────────────
# Main configuration function
# ─────────────────────────────────────────────────────────────────────────────


def configure_logging() -> None:
    """
    Configure structlog and the stdlib logging bridge.

    Must be called exactly once at application startup, before any
    logging calls are made.  Subsequent calls are safe but no-ops.
    """
    settings = get_settings()
    log_level = settings.log_level.upper()
    is_dev = settings.is_development

    # ── Shared processors ────────────────────────────────────────────────
    shared_processors = _build_shared_processors(is_dev)

    # ── Renderer ──────────────────────────────────────────────────────────
    if is_dev:
        # Human-readable colored output for local development
        renderer: Processor = structlog.dev.ConsoleRenderer(colors=True)
    else:
        # Machine-parseable JSON for production log aggregators
        renderer = structlog.processors.JSONRenderer()

    # ── Structlog config ──────────────────────────────────────────────────
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # ── Bridge stdlib logging → structlog ─────────────────────────────────
    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "structlog": {
                    "()": structlog.stdlib.ProcessorFormatter,
                    "processors": [
                        structlog.stdlib.ProcessorFormatter.remove_processors_meta,
                        rename_event_key,
                        renderer,
                    ],
                    "foreign_pre_chain": [
                        structlog.stdlib.add_log_level,
                        *shared_processors,
                    ],
                }
            },
            "handlers": {
                "default": {
                    "level": log_level,
                    "class": "logging.StreamHandler",
                    "stream": "ext://sys.stdout",
                    "formatter": "structlog",
                }
            },
            "loggers": {
                # Root logger
                "": {"handlers": ["default"], "level": log_level, "propagate": False},
                # Reduce noise from third-party libraries
                "aiogram": {"handlers": ["default"], "level": "INFO", "propagate": False},
                "aiohttp": {"handlers": ["default"], "level": "WARNING", "propagate": False},
                "sqlalchemy.engine": {
                    "handlers": ["default"],
                    "level": "DEBUG" if (is_dev and settings.db.echo) else "WARNING",
                    "propagate": False,
                },
                "celery": {"handlers": ["default"], "level": "INFO", "propagate": False},
                "apscheduler": {"handlers": ["default"], "level": "INFO", "propagate": False},
                "httpx": {"handlers": ["default"], "level": "WARNING", "propagate": False},
                "openai": {"handlers": ["default"], "level": "WARNING", "propagate": False},
            },
        }
    )


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """
    Return a structlog logger bound to the given name.

    Args:
        name: Module name, typically __name__.  Defaults to root logger.

    Returns:
        A BoundLogger that supports contextual key-value pairs.

    Example:
        log = get_logger(__name__)
        log.info("processing_update", update_id=123, user_id=456)
        log.error("database_error", exc_info=True, query="SELECT ...")
    """
    return structlog.get_logger(name)
