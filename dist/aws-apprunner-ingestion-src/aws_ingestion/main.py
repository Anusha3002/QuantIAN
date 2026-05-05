from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Query

from aws_ingestion.service import IngestionService
from shared.config import load_service_settings
from shared.runtime import ServiceRuntime
from shared.schemas import LedgerAppendRequest, MarketEvent, MarketSensorMessage

settings = load_service_settings("aws_ingestion", 8001)
runtime = ServiceRuntime(
    settings=settings,
    node_id="aws-ingestion-01",
    node_type="ingestion",
    cloud="aws",
    capabilities=["ingest_market_data", "publish_events"],
)


def _route_to_capability(
    event: MarketEvent,
    *,
    capability: str,
    path: str,
    payload: dict | None,
    routed_event_type: str,
) -> int:
    failures = 0
    for peer in runtime.peers_by_capability(capability):
        body, exc = runtime.route_with_retries(
            peer=peer,
            path=path,
            payload=payload,
            event_type=routed_event_type,
            ledger_context={"event_id": event.event_id, "symbol": event.symbol},
        )
        if exc is not None:
            failures += 1
            continue
        runtime.append_ledger(
            LedgerAppendRequest(
                event_type=routed_event_type,
                actor_node="aws-ingestion-01",
                payload={
                    "event_id": event.event_id,
                    "symbol": event.symbol,
                    "target_node": peer.node_id,
                },
            )
        )
    return failures


def route_event(event: MarketEvent) -> None:
    failures = 0
    failures += _route_to_capability(
        event,
        capability="detect_anomalies",
        path="/anomaly/analyze",
        payload=event.model_dump(),
        routed_event_type="event_routed_to_anomaly",
    )
    failures += _route_to_capability(
        event,
        capability="store_market_events",
        path="/risk/events",
        payload=event.model_dump(),
        routed_event_type="event_routed_to_risk",
    )
    # compute_risk is fire-and-forget; still pass through retry path to audit failures
    for peer in runtime.peers_by_capability("compute_risk"):
        _, exc = runtime.route_with_retries(
            peer=peer,
            path="/risk/compute",
            payload=None,
            event_type="event_routed_to_compute",
            ledger_context={"event_id": event.event_id, "symbol": event.symbol},
        )
        if exc is not None:
            failures += 1

    if failures:
        raise RuntimeError(f"{failures} downstream route(s) failed after retries")


service = IngestionService(
    node_id="aws-ingestion-01",
    ledger_appender=runtime.append_ledger if settings.enable_runtime else None,
    state_path=f"{settings.data_dir}/state.json",
    route_event=route_event if settings.enable_runtime else None,
)


@asynccontextmanager
async def lifespan(_: FastAPI):
    await runtime.start()
    yield
    await runtime.stop()


app = FastAPI(title="QuantIAN AWS Ingestion Peer", version="0.1.0", lifespan=lifespan)


@app.get("/health")
def health() -> dict[str, object]:
    return {**service.health(), "base_url": settings.base_url}


@app.post("/ingestion/messages", response_model=MarketEvent)
def ingest_message(message: MarketSensorMessage) -> MarketEvent:
    return service.ingest_message(message)


@app.post("/ingestion/events", response_model=MarketEvent)
def store_event(event: MarketEvent) -> MarketEvent:
    return service.store_normalized_event(event)


@app.get("/ingestion/events/recent", response_model=list[MarketEvent])
def recent_events(limit: int = Query(default=20, ge=1, le=200)) -> list[MarketEvent]:
    return service.recent_events(limit=limit)
