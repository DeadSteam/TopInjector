"""Async event bus using Python asyncio.Queue as a decoupled pub/sub dispatcher."""

from __future__ import annotations

import asyncio
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass(slots=True)
class Event:
    """Domain event carrying payload."""

    type: str
    payload: dict[str, Any] = field(default_factory=dict)


class EventBus:
    """Lightweight in-process async event bus for decoupling module boundaries.

    Usage::

        bus = EventBus()
        bus.subscribe("task.completed", my_handler)
        await bus.publish(Event(type="task.completed", payload={...}))
    """

    def __init__(self) -> None:  # noqa: D401
        self._handlers: dict[str, list[Callable]] = defaultdict(list)
        self._queue: asyncio.Queue[Event] = asyncio.Queue(maxsize=4096)

    # -- registration -------------------------------------------------------- #

    def subscribe(self, event_type: str, handler: Callable) -> None:
        """Register *handler* for *event_type*.

        Handlers may be regular functions or ``async def``.  The bus inspects
        at dispatch time so both patterns are supported.
        """
        self._handlers[event_type].append(handler)

    # -- publishing ---------------------------------------------------------- #

    async def publish(self, event: Event) -> None:
        """Enqueue *event* for dispatch to all subscribers."""
        await self._queue.put(event)

    async def publish_immediate(self, event: Event) -> None:
        """Dispatch immediately without going through the queue (use inside handlers)."""
        await self._dispatch(event)

    # -- internal dispatch --------------------------------------------------- #

    async def _dispatch(self, event: Event) -> None:
        handlers = self._handlers.get(event.type, [])
        for handler in handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(event)  # type: ignore[possibly-undefined]
                else:
                    handler(event)
            except Exception:
                # Log but don't propagate — one bad handler shouldn't kill others
                import logging

                logging.exception("Error in event handler for %s", event.type)

    async def worker(self) -> None:
        """Run this coroutine to drain the queue and dispatch events."""
        while True:
            event = await self._queue.get()
            await self._dispatch(event)
            self._queue.task_done()


# Singleton for the application lifecycle
_default_bus: EventBus | None = None


def get_bus() -> EventBus:
    global _default_bus
    if _default_bus is None:
        _default_bus = EventBus()
    return _default_bus
