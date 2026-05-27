"""
infrastructure.error_logger
~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Centralized exception logger that persists unhandled errors to the
system_errors table for post-mortem analysis.

Usage:
    from infrastructure.error_logger import log_system_error

    try:
        ...
    except Exception as exc:
        await log_system_error("bot", exc)

All methods are fire-and-forget: they never raise.
"""

from __future__ import annotations

import traceback

from shared.logging import get_logger

log = get_logger(__name__)


async def log_system_error(
    service: str,
    exc: BaseException,
    *,
    message: str | None = None,
) -> None:
    """Persist an exception to system_errors. Never raises.

    Args:
        service: Origin service name (e.g. "bot", "scheduler", "celery").
        exc: The caught exception.
        message: Optional override for exc message.
    """
    try:
        from infrastructure.database.models.system_error import SystemErrorModel
        from infrastructure.database.session import get_session_factory

        error_type = type(exc).__qualname__
        error_msg = message or str(exc)
        stack = traceback.format_exception(type(exc), exc, exc.__traceback__)
        stacktrace = "".join(stack)

        # Truncate to avoid bloating the table
        if len(error_msg) > 2000:
            error_msg = error_msg[:2000] + "..."
        if len(stacktrace) > 8000:
            stacktrace = stacktrace[:8000] + "\n... truncated"

        factory = get_session_factory()
        async with factory() as session:
            session.add(
                SystemErrorModel(
                    service=service[:64],
                    error_type=error_type[:256],
                    message=error_msg,
                    stacktrace=stacktrace,
                )
            )
            await session.commit()

    except Exception:
        # Last resort: structured log so we don't lose the error entirely
        log.error(
            "system_error_log_failed",
            service=service,
            original_error=str(exc),
            exc_info=True,
        )
