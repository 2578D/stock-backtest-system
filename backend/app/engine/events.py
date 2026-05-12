"""Event system for the backtest engine.

Events flow: BAR → ORDER → FILL → PORTFOLIO
"""

from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import Any, Callable


class EventType(Enum):
    BAR = "bar"                # Market bar arrives
    ORDER = "order"            # Strategy emits order
    FILL = "fill"              # Order filled
    RISK_REJECT = "risk_reject"  # Order rejected by risk manager
    PORTFOLIO = "portfolio"    # Portfolio snapshot


@dataclass
class Event:
    type: EventType
    timestamp: date
    data: dict[str, Any] = field(default_factory=dict)


Handler = Callable[[Event], None]


class EventBus:
    """Simple publish-subscribe event bus."""

    def __init__(self):
        self._handlers: dict[EventType, list[Handler]] = {t: [] for t in EventType}

    def subscribe(self, event_type: EventType, handler: Handler) -> None:
        self._handlers[event_type].append(handler)

    def publish(self, event: Event) -> None:
        for handler in self._handlers[event.type]:
            handler(event)
