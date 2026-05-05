from __future__ import annotations

from pathlib import Path
from typing import Callable

from shared.schemas import MarketEvent, MarketSensorMessage
from shared.storage import load_json_file, save_json_file
from shared.utils.ids import make_prefixed_id
from shared.utils.ledger import LedgerAppender, record_ledger_event

RouteEvent = Callable[[MarketEvent], None]


class IngestionService:
    def __init__(
        self,
        node_id: str,
        ledger_appender: LedgerAppender | None = None,
        *,
        state_path: str | Path | None = None,
        route_event: RouteEvent | None = None,
    ) -> None:
        self.node_id = node_id
        self.ledger_appender = ledger_appender
        self.state_path = Path(state_path) if state_path is not None else None
        self.route_event = route_event
        self.raw_messages: list[MarketSensorMessage] = []
        self.events: list[MarketEvent] = []
        self._last_message_by_symbol: dict[str, MarketSensorMessage] = {}
        self.forwarded_events = 0
        self.routing_failures = 0
        self._load_state()

    def ingest_message(self, message: MarketSensorMessage) -> MarketEvent:
        previous = self._last_message_by_symbol.get(message.symbol)
        price_change = 0.0
        volume_change = 0.0
        if previous is not None:
            if previous.price:
                price_change = (message.price - previous.price) / previous.price
            if previous.volume:
                volume_change = (message.volume - previous.volume) / previous.volume

        event = MarketEvent(
            event_id=make_prefixed_id("evt"),
            symbol=message.symbol,
            asset_class=message.asset_class,
            price=round(message.price, 6),
            volume=round(message.volume, 6),
            source=self.node_id,
            window={
                "price_change_1m": round(price_change, 6),
                "volume_change_1m": round(volume_change, 6),
                "notional_value": round(message.price * message.volume, 6),
            },
        )

        self.raw_messages.append(message)
        self.events.append(event)
        self._last_message_by_symbol[message.symbol] = message
        self._save_state()

        record_ledger_event(
            self.ledger_appender,
            event_type="market_event_ingested",
            actor_node=self.node_id,
            payload=event.model_dump(),
        )
        self._forward_event(event)
        return event

    def store_normalized_event(self, event: MarketEvent) -> MarketEvent:
        self.events.append(event)
        self._save_state()
        record_ledger_event(
            self.ledger_appender,
            event_type="market_event_stored",
            actor_node=self.node_id,
            payload=event.model_dump(),
        )
        return event

    def recent_events(self, limit: int = 20) -> list[MarketEvent]:
        return self.events[-limit:]

    def health(self) -> dict[str, object]:
        return {
            "status": "ok",
            "service": "aws_ingestion",
            "node_id": self.node_id,
            "raw_messages": len(self.raw_messages),
            "normalized_events": len(self.events),
            "forwarded_events": self.forwarded_events,
            "routing_failures": self.routing_failures,
        }

    def _forward_event(self, event: MarketEvent) -> None:
        if self.route_event is None:
            return
        try:
            self.route_event(event)
            self.forwarded_events += 1
        except Exception:
            self.routing_failures += 1

    def _load_state(self) -> None:
        payload = load_json_file(self.state_path, {"raw_messages": [], "events": []})
        self.raw_messages = [MarketSensorMessage.model_validate(item) for item in payload.get("raw_messages", [])]
        self.events = [MarketEvent.model_validate(item) for item in payload.get("events", [])]
        self._last_message_by_symbol = {message.symbol: message for message in self.raw_messages}

    def _save_state(self) -> None:
        save_json_file(
            self.state_path,
            {
                "raw_messages": [message.model_dump() for message in self.raw_messages],
                "events": [event.model_dump() for event in self.events],
            },
        )
