from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from aws_ingestion.service import IngestionService
from azure_anomaly.service import AnomalyService
from gcp_risk.service import RiskService
from registry_service.store import InMemoryRegistryStore
from shared.schemas import LedgerAppendRequest, PeerHeartbeat, PeerRegistration, Portfolio, PortfolioPosition
from simulator.mqtt_publisher import MarketSensorSimulator


def register_peer(store: InMemoryRegistryStore, peer: PeerRegistration) -> None:
    registered = store.upsert_peer(peer)
    store.append_block(
        LedgerAppendRequest(
            event_type="peer_registered",
            actor_node=peer.node_id,
            payload=registered.model_dump(),
        )
    )
    store.heartbeat(peer.node_id, PeerHeartbeat())


def main() -> None:
    store = InMemoryRegistryStore()
    ledger_appender = store.append_block

    register_peer(
        store,
        PeerRegistration(
            node_id="registry-01",
            node_type="registry",
            cloud="shared",
            base_url="http://localhost:8000",
            capabilities=["register_peers", "track_heartbeats", "append_ledger"],
        ),
    )
    register_peer(
        store,
        PeerRegistration(
            node_id="aws-ingestion-01",
            node_type="ingestion",
            cloud="aws",
            base_url="http://localhost:8001",
            capabilities=["ingest_market_data", "publish_events"],
        ),
    )
    register_peer(
        store,
        PeerRegistration(
            node_id="azure-anomaly-01",
            node_type="anomaly",
            cloud="azure",
            base_url="http://localhost:8002",
            capabilities=["detect_anomalies", "list_alerts", "submit_review_feedback"],
        ),
    )
    register_peer(
        store,
        PeerRegistration(
            node_id="gcp-risk-01",
            node_type="risk",
            cloud="gcp",
            base_url="http://localhost:8003",
            capabilities=["compute_risk", "list_risk_history"],
        ),
    )

    ingestion = IngestionService(node_id="aws-ingestion-01", ledger_appender=ledger_appender)
    anomaly = AnomalyService(node_id="azure-anomaly-01", ledger_appender=ledger_appender)
    risk = RiskService(node_id="gcp-risk-01", ledger_appender=ledger_appender)
    risk.set_portfolio(
        Portfolio(
            portfolio_id="demo_portfolio",
            positions=[
                PortfolioPosition(symbol="BTCUSD", weight=0.4),
                PortfolioPosition(symbol="ETHUSD", weight=0.3),
                PortfolioPosition(symbol="AAPL", weight=0.2),
                PortfolioPosition(symbol="MSFT", weight=0.1),
            ],
        )
    )

    simulator = MarketSensorSimulator(seed=7)
    alerts_created = []
    for cycle in range(18):
        anomaly_symbol = "BTCUSD" if cycle == 10 else None
        messages = simulator.generate_cycle(anomaly_symbol=anomaly_symbol)
        for message in messages:
            event = ingestion.ingest_message(message)
            risk.ingest_event(event)
            alert = anomaly.analyze_event(event)
            if alert is not None:
                alerts_created.append(alert)

    latest_risk = risk.compute_risk()
    summary = {
        "peers": [peer.model_dump() for peer in store.list_peers()],
        "events_processed": len(ingestion.events),
        "alerts_created": len(alerts_created),
        "latest_alert": alerts_created[-1].model_dump() if alerts_created else None,
        "latest_risk": latest_risk.model_dump(),
        "ledger_valid": store.verify_ledger().model_dump(),
        "ledger_blocks": len(store.list_blocks()),
    }
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
