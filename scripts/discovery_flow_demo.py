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
os.environ["QUANTIAN_DATA_DIR"] = str(REPO_ROOT / "data" / "test_discovery_flow")
shutil.rmtree(Path(os.environ["QUANTIAN_DATA_DIR"]), ignore_errors=True)

from aws_ingestion.main import app as ingestion_app
from azure_anomaly.main import app as anomaly_app
from gcp_risk.main import app as risk_app
from registry_service.main import app as registry_app
from simulator.mqtt_publisher import MarketSensorSimulator


def register_peer(client: TestClient, payload: dict[str, object]) -> None:
    client.post("/registry/peers", json=payload)
    client.post(f"/registry/peers/{payload['node_id']}/heartbeat", json={})


def first_peer_for_capability(registry: TestClient, capability: str) -> dict[str, object]:
    response = registry.get(f"/registry/capabilities/{capability}")
    response.raise_for_status()
    matches = response.json()
    if not matches:
        raise RuntimeError(f"no peers registered for capability {capability}")
    return matches[0]


def append_ledger_block(registry: TestClient, *, event_type: str, actor_node: str, payload: dict[str, object]) -> None:
    registry.post(
        "/ledger/blocks",
        json={
            "event_type": event_type,
            "actor_node": actor_node,
            "payload": payload,
        },
    )


def main() -> None:
    registry = TestClient(registry_app)
    ingestion = TestClient(ingestion_app)
    anomaly = TestClient(anomaly_app)
    risk = TestClient(risk_app)

    client_by_base_url = {
        "http://localhost:8001": ingestion,
        "http://localhost:8002": anomaly,
        "http://localhost:8003": risk,
    }

    register_peer(
        registry,
        {
            "node_id": "aws-ingestion-01",
            "node_type": "ingestion",
            "cloud": "aws",
            "base_url": "http://localhost:8001",
            "capabilities": ["ingest_market_data", "publish_events"],
        },
    )
    register_peer(
        registry,
        {
            "node_id": "azure-anomaly-01",
            "node_type": "anomaly",
            "cloud": "azure",
            "base_url": "http://localhost:8002",
            "capabilities": ["detect_anomalies", "list_alerts", "submit_review_feedback"],
        },
    )
    register_peer(
        registry,
        {
            "node_id": "gcp-risk-01",
            "node_type": "risk",
            "cloud": "gcp",
            "base_url": "http://localhost:8003",
            "capabilities": ["compute_risk", "list_risk_history", "store_market_events"],
        },
    )

    risk.post(
        "/risk/portfolio",
        json={
            "portfolio_id": "demo_portfolio",
            "positions": [
                {"symbol": "BTCUSD", "weight": 0.4},
                {"symbol": "ETHUSD", "weight": 0.3},
                {"symbol": "AAPL", "weight": 0.2},
                {"symbol": "MSFT", "weight": 0.1},
            ],
        },
    )

    simulator = MarketSensorSimulator(seed=17)
    routed_alerts = 0

    for cycle in range(14):
        anomaly_symbol = "BTCUSD" if cycle == 8 else None
        for message in simulator.generate_cycle(anomaly_symbol=anomaly_symbol):
            ingestion_response = ingestion.post("/ingestion/messages", json=message.model_dump())
            event = ingestion_response.json()

            anomaly_peer = first_peer_for_capability(registry, "detect_anomalies")
            anomaly_response = client_by_base_url[str(anomaly_peer["base_url"])].post("/anomaly/analyze", json=event)
            alert = anomaly_response.json()

            risk_peer = first_peer_for_capability(registry, "compute_risk")
            client_by_base_url[str(risk_peer["base_url"])].post("/risk/events", json=event)

            append_ledger_block(
                registry,
                event_type="event_routed",
                actor_node="aws-ingestion-01",
                payload={
                    "event_id": event["event_id"],
                    "symbol": event["symbol"],
                    "anomaly_peer": anomaly_peer["node_id"],
                    "risk_peer": risk_peer["node_id"],
                },
            )
            if alert is not None:
                routed_alerts += 1
                append_ledger_block(
                    registry,
                    event_type="alert_forwarded",
                    actor_node="azure-anomaly-01",
                    payload=alert,
                )

    latest_risk = risk.post("/risk/compute").json()
    summary = {
        "registered_peers": registry.get("/registry/peers").json(),
        "alerts": anomaly.get("/anomaly/alerts").json(),
        "routed_alert_count": routed_alerts,
        "risk_snapshot": latest_risk,
        "ledger_verification": registry.get("/ledger/verify").json(),
        "ledger_block_count": len(registry.get("/ledger/blocks").json()),
    }
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
