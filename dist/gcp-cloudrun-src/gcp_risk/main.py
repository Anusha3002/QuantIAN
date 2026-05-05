from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import Body, FastAPI, HTTPException, status

from gcp_risk.service import RiskService
from shared.config import load_service_settings
from shared.runtime import ServiceRuntime
from shared.schemas import MarketEvent, Portfolio, RiskSnapshot

settings = load_service_settings("gcp_risk", 8003)
runtime = ServiceRuntime(
    settings=settings,
    node_id="gcp-risk-01",
    node_type="risk",
    cloud="gcp",
    capabilities=["compute_risk", "list_risk_history", "store_market_events"],
)
service = RiskService(
    node_id="gcp-risk-01",
    ledger_appender=runtime.append_ledger if settings.enable_runtime else None,
    state_path=f"{settings.data_dir}/state.json",
    auto_compute=True,
)


@asynccontextmanager
async def lifespan(_: FastAPI):
    await runtime.start()
    yield
    await runtime.stop()


app = FastAPI(title="QuantIAN GCP Risk Peer", version="0.1.0", lifespan=lifespan)


@app.get("/health")
def health() -> dict[str, object]:
    return {**service.health(), "base_url": settings.base_url}


@app.post("/risk/events", response_model=MarketEvent)
def ingest_event(event: MarketEvent) -> MarketEvent:
    return service.ingest_event(event)


@app.post("/risk/portfolio", response_model=Portfolio)
def set_portfolio(portfolio: Portfolio) -> Portfolio:
    return service.set_portfolio(portfolio)


@app.get("/risk/portfolio", response_model=Portfolio)
def get_portfolio() -> Portfolio:
    portfolio = service.get_portfolio()
    if portfolio is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="no portfolio configured")
    return portfolio


@app.post("/risk/compute", response_model=RiskSnapshot)
def compute_risk(portfolio: Portfolio | None = Body(default=None)) -> RiskSnapshot:
    try:
        return service.compute_risk(portfolio)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@app.get("/risk/latest", response_model=RiskSnapshot)
def latest_snapshot() -> RiskSnapshot:
    snapshot = service.latest_snapshot()
    if snapshot is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="no risk snapshot available")
    return snapshot


@app.get("/risk/history", response_model=list[RiskSnapshot])
def snapshot_history() -> list[RiskSnapshot]:
    return service.snapshot_history()
