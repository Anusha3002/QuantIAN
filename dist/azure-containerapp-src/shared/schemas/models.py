from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from shared.utils.time import utc_now


class PeerStatus(StrEnum):
    ONLINE = "online"
    STALE = "stale"
    OFFLINE = "offline"


class PeerRegistration(BaseModel):
    model_config = ConfigDict(extra="allow")

    node_id: str = Field(min_length=3, max_length=128)
    node_type: str = Field(min_length=3, max_length=64)
    cloud: Literal["aws", "azure", "gcp", "local", "shared"]
    base_url: str = Field(min_length=1, max_length=512)
    capabilities: list[str] = Field(default_factory=list)
    status: PeerStatus = PeerStatus.ONLINE
    last_heartbeat: str = Field(default_factory=utc_now)
    metadata: dict[str, Any] = Field(default_factory=dict)


class PeerHeartbeat(BaseModel):
    status: PeerStatus = PeerStatus.ONLINE
    observed_at: str = Field(default_factory=utc_now)


class MarketSensorMessage(BaseModel):
    sensor_id: str
    symbol: str
    asset_class: Literal["crypto", "equity", "forex", "commodity"]
    price: float
    volume: float
    source: str
    event_time: str = Field(default_factory=utc_now)


class MarketEvent(BaseModel):
    event_id: str
    symbol: str
    asset_class: str
    price: float
    volume: float
    source: str
    ingested_at: str = Field(default_factory=utc_now)
    window: dict[str, float] = Field(default_factory=dict)


class AnomalyAlert(BaseModel):
    alert_id: str
    event_id: str
    symbol: str
    severity: Literal["low", "medium", "high", "critical"]
    score: float
    reason: str
    status: Literal["pending_review", "confirmed", "false_positive", "dismissed"]
    created_at: str = Field(default_factory=utc_now)


class AnomalyAlertReview(BaseModel):
    reviewer: str
    status: Literal["confirmed", "false_positive", "dismissed"]
    notes: str | None = None
    reviewed_at: str = Field(default_factory=utc_now)


class PortfolioPosition(BaseModel):
    symbol: str
    weight: float


class Portfolio(BaseModel):
    portfolio_id: str
    positions: list[PortfolioPosition]


class RiskSnapshot(BaseModel):
    snapshot_id: str
    portfolio_id: str
    as_of: str = Field(default_factory=utc_now)
    volatility: float
    value_at_risk_95: float
    max_drawdown: float
    rolling_return_1d: float


class LedgerAppendRequest(BaseModel):
    event_type: str = Field(min_length=3, max_length=128)
    actor_node: str = Field(min_length=3, max_length=128)
    payload: dict[str, Any] = Field(default_factory=dict)


class LedgerBlock(BaseModel):
    block_id: int
    timestamp: str = Field(default_factory=utc_now)
    event_type: str
    actor_node: str
    payload_hash: str
    previous_hash: str | None = None
    block_hash: str


class LedgerVerificationResult(BaseModel):
    valid: bool
    block_count: int
    error: str | None = None
