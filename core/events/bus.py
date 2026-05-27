"""
In-process domain event bus.
Decouples event emitters from event handlers.
"""
from __future__ import annotations

import asyncio
from collections import defaultdict
from collections.abc import Callable, Coroutine
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from shared.logging import get_logger

log = get_logger(__name__)

Handler = Callable[..., Coroutine[Any, Any, None]]


@dataclass(frozen=True)
class DomainEvent:
    """Base class for all domain events."""
    occurred_at: datetime = field(default_factory=datetime.utcnow)


@dataclass(frozen=True)
class LeadCreated(DomainEvent):
    lead_id: int = 0
    user_id: int = 0
    category: str = ""
    source: str = ""


@dataclass(frozen=True)
class StageChanged(DomainEvent):
    lead_id: int = 0
    from_stage: str = ""
    to_stage: str = ""
    actor_id: int = 0


@dataclass(frozen=True)
class AppointmentBooked(DomainEvent):
    appointment_id: int = 0
    lead_id: int = 0
    installer_id: int | None = None
    scheduled_at: datetime = field(default_factory=datetime.utcnow)


@dataclass(frozen=True)
class BroadcastCompleted(DomainEvent):
    broadcast_id: int = 0
    sent_count: int = 0
    failed_count: int = 0


class EventBus:
    """
    Simple async in-process event bus.
    Handlers are registered with @bus.subscribe(EventClass).
    Events are emitted with await bus.emit(event_instance).
    All handlers run concurrently via asyncio.gather.
    """

    def __init__(self) -> None:
        self._handlers: dict[type, list[Handler]] = defaultdict(list)

    def subscribe(self, event_type: type) -> Callable[[Handler], Handler]:
        """Decorator to register a handler for an event type."""
        def decorator(handler: Handler) -> Handler:
            self._handlers[event_type].append(handler)
            log.debug("event_handler_registered", event=event_type.__name__, handler=handler.__name__)
            return handler
        return decorator

    async def emit(self, event: DomainEvent) -> None:
        """Emit an event and run all registered handlers concurrently."""
        handlers = self._handlers.get(type(event), [])
        if not handlers:
            return
        log.debug("event_emitted", event=type(event).__name__, handler_count=len(handlers))
        await asyncio.gather(*[h(event) for h in handlers], return_exceptions=True)


# Global event bus singleton
event_bus = EventBus()
