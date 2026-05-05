from __future__ import annotations

from collections.abc import Callable
from typing import Any

from shared.schemas import LedgerAppendRequest

LedgerAppender = Callable[[LedgerAppendRequest], object]


def record_ledger_event(
    appender: LedgerAppender | None,
    *,
    event_type: str,
    actor_node: str,
    payload: dict[str, Any],
) -> None:
    if appender is None:
        return
    appender(
        LedgerAppendRequest(
            event_type=event_type,
            actor_node=actor_node,
            payload=payload,
        )
    )
