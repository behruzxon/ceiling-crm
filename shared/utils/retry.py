"""
shared.utils.retry
~~~~~~~~~~~~~~~~~~
Reusable async retry helper with exponential backoff.

Usage:
    from shared.utils.retry import with_retry

    result = await with_retry(
        some_async_func, arg1, arg2,
        max_retries=3,
        base_delay=1.0,
        retryable=(ConnectionError, TimeoutError),
    )

Or as a decorator:
    @retry(max_retries=3, base_delay=1.0, retryable=(ConnectionError,))
    async def flaky_call():
        ...
"""

from __future__ import annotations

import asyncio
import functools
from collections.abc import Callable
from typing import Any, TypeVar

from shared.logging import get_logger

log = get_logger(__name__)

T = TypeVar("T")

# Default delays: 1s, 2s, 4s (exponential)
_DEFAULT_MAX_RETRIES = 3
_DEFAULT_BASE_DELAY = 1.0
_DEFAULT_BACKOFF_FACTOR = 2.0


async def with_retry(
    func: Callable[..., Any],
    *args: Any,
    max_retries: int = _DEFAULT_MAX_RETRIES,
    base_delay: float = _DEFAULT_BASE_DELAY,
    backoff_factor: float = _DEFAULT_BACKOFF_FACTOR,
    retryable: tuple[type[BaseException], ...] = (Exception,),
    operation: str = "",
    **kwargs: Any,
) -> Any:
    """Call *func* with retries on specified exceptions.

    Args:
        func: Async callable to invoke.
        max_retries: Maximum number of retry attempts (not counting the first call).
        base_delay: Initial delay between retries in seconds.
        backoff_factor: Multiplier applied to delay after each retry.
        retryable: Exception types that trigger a retry.
        operation: Human-readable name for logging (e.g. "openai_call").

    Returns:
        The result of *func*.

    Raises:
        The last exception if all retries are exhausted.
    """
    op_name = operation or getattr(func, "__name__", "unknown")
    last_exc: BaseException | None = None
    delay = base_delay

    for attempt in range(1, max_retries + 2):  # attempt 1 = first call
        try:
            return await func(*args, **kwargs)
        except retryable as exc:
            last_exc = exc
            if attempt > max_retries:
                log.warning(
                    "retry_exhausted",
                    operation=op_name,
                    attempts=attempt,
                    error=str(exc),
                )
                raise
            log.info(
                "retry_attempt",
                operation=op_name,
                attempt=attempt,
                max_retries=max_retries,
                delay=delay,
                error=str(exc),
            )
            await asyncio.sleep(delay)
            delay *= backoff_factor

    raise last_exc  # type: ignore[misc]  # unreachable but satisfies type checker


def retry(
    *,
    max_retries: int = _DEFAULT_MAX_RETRIES,
    base_delay: float = _DEFAULT_BASE_DELAY,
    backoff_factor: float = _DEFAULT_BACKOFF_FACTOR,
    retryable: tuple[type[BaseException], ...] = (Exception,),
    operation: str = "",
) -> Callable:
    """Decorator version of :func:`with_retry`."""

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            return await with_retry(
                func,
                *args,
                max_retries=max_retries,
                base_delay=base_delay,
                backoff_factor=backoff_factor,
                retryable=retryable,
                operation=operation or func.__name__,
                **kwargs,
            )

        return wrapper

    return decorator
