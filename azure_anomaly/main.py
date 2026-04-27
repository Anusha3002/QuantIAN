from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, status

from azure_anomaly.service import AnomalyService
from shared.config import load_service_settings
from shared.runtime import ServiceRuntime
from shared.schemas import AnomalyAlert, AnomalyAlertReview, MarketEvent
from shared.storage import build_json_state_store

settings = load_service_settings("azure_anomaly", 8002)
runtime = ServiceRuntime(
    settings=settings,
    node_id="azure-anomaly-01",
    node_type="anomaly",
    cloud="azure",
    capabilities=["detect_anomalies", "list_alerts", "submit_review_feedback"],
)
service = AnomalyService(
    node_id="azure-anomaly-01",
    ledger_appender=runtime.append_ledger if settings.enable_runtime else None,
    state_path=f"{settings.data_dir}/state.json",
    state_store=build_json_state_store(
        settings=settings,
        state_path=f"{settings.data_dir}/state.json",
        service_name="azure_anomaly",
        default_blob_name="azure-anomaly/state.json",
    ),
)


@asynccontextmanager
async def lifespan(_: FastAPI):
    await runtime.start()
    yield
    await runtime.stop()


app = FastAPI(title="QuantIAN Azure Anomaly Peer", version="0.1.0", lifespan=lifespan)


@app.get("/health")
def health() -> dict[str, object]:
    return {**service.health(), "base_url": settings.base_url}


@app.post("/anomaly/analyze", response_model=AnomalyAlert | None)
def analyze_event(event: MarketEvent) -> AnomalyAlert | None:
    return service.analyze_event(event)


@app.get("/anomaly/alerts", response_model=list[AnomalyAlert])
def list_alerts() -> list[AnomalyAlert]:
    return service.list_alerts()


@app.get("/anomaly/alerts/{alert_id}", response_model=AnomalyAlert)
def get_alert(alert_id: str) -> AnomalyAlert:
    alert = service.get_alert(alert_id)
    if alert is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="alert not found")
    return alert


@app.post("/anomaly/alerts/{alert_id}/review", response_model=AnomalyAlert)
def review_alert(alert_id: str, review: AnomalyAlertReview) -> AnomalyAlert:
    alert = service.get_alert(alert_id)
    if alert is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="alert not found")
    return service.review_alert(alert_id, review)
