# Blueprint 03 — Logical View

| Legend Box                  | Value                                                           |
|-----------------------------|-----------------------------------------------------------------|
| **Architecture Domain**     | Application + Data                                              |
| **Blueprint Type**          | Service Interaction / Information Flow Diagram                  |
| **Scope**                   | Project                                                         |
| **Level of Abstraction**    | Logical                                                         |
| **State**                   | To-Be                                                           |
| **Communication Objective** | Concrete endpoints, schemas, and the tick-to-ledger lifecycle   |
| **Authors**                 | QuantIAN Team                                                   |
| **Revision Date**           | 2026-04-21                                                      |
| **Status**                  | Working Draft                                                   |

## Service-level sequence

```mermaid
sequenceDiagram
    autonumber
    participant Sim as Market Sensor Simulator
    participant MQTT as MQTT Broker<br/>(Mosquitto)
    participant Bridge as IoT Bridge<br/>(:8014)
    participant Ing as AWS Ingestion<br/>(:8011)
    participant Reg as Registry + Ledger<br/>(:8010)
    participant Anom as Azure Anomaly<br/>(:8012)
    participant Risk as GCP Risk<br/>(:8013)

    Note over Reg: Peers registered + heartbeating on startup
    Sim->>MQTT: publish quantian/market/crypto/BTCUSD<br/>{sensor_id, symbol, price, volume, ...}
    MQTT->>Bridge: deliver (QoS 1)
    Bridge->>Bridge: MarketSensorMessage validation
    Bridge->>Ing: POST /ingestion/messages
    Ing->>Reg: POST /ledger/blocks<br/>event_type=market_event_ingested
    Ing->>Reg: GET /registry/capabilities/detect_anomalies
    Reg-->>Ing: [PeerRegistration]
    Ing->>Anom: POST /anomaly/analyze (MarketEvent)<br/>with retries
    Ing->>Reg: POST /ledger/blocks<br/>event_type=event_routed_to_anomaly
    Ing->>Reg: GET /registry/capabilities/store_market_events
    Reg-->>Ing: [PeerRegistration]
    Ing->>Risk: POST /risk/events (MarketEvent)<br/>with retries
    Ing->>Reg: POST /ledger/blocks<br/>event_type=event_routed_to_risk
    Anom->>Anom: features = window deltas + price + volume
    Anom->>Anom: score = max(rule_based, isolation_forest)
    alt score ≥ 0.82
        Anom->>Anom: create AnomalyAlert
        Anom->>Reg: POST /ledger/blocks<br/>event_type=anomaly_alert_created
    end
    Risk->>Risk: append to events_by_symbol
    Ing->>Risk: POST /risk/compute (if auto_compute)
    Risk->>Risk: vol · VaR95 · max DD · 1d return
    Risk->>Reg: POST /ledger/blocks<br/>event_type=risk_snapshot_computed
    Note over Reg: Auto-verifier re-walks the chain every 60 s
```

## Capability map

| Capability                 | Declared by      | Consumed by       |
|----------------------------|------------------|-------------------|
| `ingest_market_data`       | aws-ingestion-01 | iot-bridge-01     |
| `publish_events`           | aws-ingestion-01 | —                 |
| `collect_edge_telemetry`   | iot-bridge-01    | (operators)       |
| `mqtt_bridge`              | iot-bridge-01    | —                 |
| `detect_anomalies`         | azure-anomaly-01 | aws-ingestion-01  |
| `list_alerts`              | azure-anomaly-01 | operators         |
| `submit_review_feedback`   | azure-anomaly-01 | operators         |
| `compute_risk`             | gcp-risk-01      | aws-ingestion-01  |
| `store_market_events`      | gcp-risk-01      | aws-ingestion-01  |
| `list_risk_history`        | gcp-risk-01      | operators         |

## Data contracts (Pydantic, see [`shared/schemas/models.py`](../../shared/schemas/models.py))

```mermaid
classDiagram
    class MarketSensorMessage {
      str sensor_id
      str symbol
      str asset_class
      float price
      float volume
      str source
      str event_time
    }
    class MarketEvent {
      str event_id
      str symbol
      str asset_class
      float price
      float volume
      str source
      str ingested_at
      dict window
    }
    class AnomalyAlert {
      str alert_id
      str event_id
      str symbol
      str severity
      float score
      str reason
      str status
      str created_at
    }
    class RiskSnapshot {
      str snapshot_id
      str portfolio_id
      str as_of
      float volatility
      float value_at_risk_95
      float max_drawdown
      float rolling_return_1d
    }
    class LedgerBlock {
      int block_id
      str timestamp
      str event_type
      str actor_node
      str payload_hash
      str previous_hash
      str block_hash
    }
    MarketSensorMessage --> MarketEvent : normalize
    MarketEvent --> AnomalyAlert : may produce
    MarketEvent --> RiskSnapshot : aggregated into
    AnomalyAlert --> LedgerBlock : block recorded
    RiskSnapshot --> LedgerBlock : block recorded
    MarketEvent --> LedgerBlock : block recorded
```

## Endpoint surface at a glance

- Registry / ledger — [`registry_service/main.py`](../../registry_service/main.py)
- AWS Ingestion — [`aws_ingestion/main.py`](../../aws_ingestion/main.py)
- Azure Anomaly — [`azure_anomaly/main.py`](../../azure_anomaly/main.py)
- GCP Risk — [`gcp_risk/main.py`](../../gcp_risk/main.py)
- IoT Bridge — [`iot/main.py`](../../iot/main.py)

Full endpoint list is in the [root README](../../README.md#core-endpoints-reference).
