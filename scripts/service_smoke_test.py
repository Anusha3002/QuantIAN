from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path

from fastapi.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
os.environ["ENABLE_SERVICE_RUNTIME"] = "false"
os.environ["QUANTIAN_DATA_DIR"] = str(REPO_ROOT / "data" / "test_service_smoke")
shutil.rmtree(Path(os.environ["QUANTIAN_DATA_DIR"]), ignore_errors=True)

from aws_ingestion.main import app as ingestion_app
from azure_anomaly.main import app as anomaly_app
from gcp_risk.main import app as risk_app
from registry_service.main import app as registry_app


def main() -> None:
    registry = TestClient(registry_app)
    ingestion = TestClient(ingestion_app)
    anomaly = TestClient(anomaly_app)
    risk = TestClient(risk_app)

    peer_payload = {
        "node_id": "aws-ingestion-01",
        "node_type": "ingestion",
        "cloud": "aws",
        "base_url": "http://localhost:8001",
        "capabilities": ["ingest_market_data", "publish_events"],
    }
    register_response = registry.post("/registry/peers", json=peer_payload)
    heartbeat_response = registry.post("/registry/peers/aws-ingestion-01/heartbeat", json={})
    capability_response = registry.get("/registry/capabilities/ingest_market_data")

    message_payload = {
        "sensor_id": "sensor-btcusd",
        "symbol": "BTCUSD",
        "asset_class": "crypto",
        "price": 71000.0,
        "volume": 185000.0,
        "source": "smoke-test",
    }
    event_one = ingestion.post("/ingestion/messages", json=message_payload)
    message_payload["price"] = 78000.0
    message_payload["volume"] = 305000.0
    event_two = ingestion.post("/ingestion/messages", json=message_payload)

    alert_response = anomaly.post("/anomaly/analyze", json=event_two.json())
    alerts_response = anomaly.get("/anomaly/alerts")

    portfolio_response = risk.post(
        "/risk/portfolio",
        json={
            "portfolio_id": "demo_portfolio",
            "positions": [
                {"symbol": "BTCUSD", "weight": 0.6},
                {"symbol": "ETHUSD", "weight": 0.4},
            ],
        },
    )
    risk.post(
        "/risk/events",
        json={
            "event_id": "evt_eth_1",
            "symbol": "ETHUSD",
            "asset_class": "crypto",
            "price": 3200.0,
            "volume": 120000.0,
            "source": "smoke-test",
            "window": {"price_change_1m": 0.0, "volume_change_1m": 0.0},
        },
    )
    risk.post(
        "/risk/events",
        json={
            "event_id": "evt_eth_2",
            "symbol": "ETHUSD",
            "asset_class": "crypto",
            "price": 3340.0,
            "volume": 180000.0,
            "source": "smoke-test",
            "window": {"price_change_1m": 0.04375, "volume_change_1m": 0.5},
        },
    )
    risk.post("/risk/events", json=event_one.json())
    risk.post("/risk/events", json=event_two.json())
    compute_response = risk.post("/risk/compute")
    ledger_response = registry.get("/ledger/verify")

    summary = {
        "registry": {
            "register_status": register_response.status_code,
            "heartbeat_status": heartbeat_response.status_code,
            "capability_matches": len(capability_response.json()),
        },
        "ingestion": {
            "first_event_status": event_one.status_code,
            "second_event_status": event_two.status_code,
            "recent_events": len(ingestion.get("/ingestion/events/recent").json()),
        },
        "anomaly": {
            "analyze_status": alert_response.status_code,
            "alert_returned": alert_response.json() is not None,
            "stored_alerts": len(alerts_response.json()),
        },
        "risk": {
            "portfolio_status": portfolio_response.status_code,
            "compute_status": compute_response.status_code,
            "latest_snapshot": compute_response.json(),
        },
        "ledger": ledger_response.json(),
    }
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
