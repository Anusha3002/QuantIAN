# Blueprint 02 — Conceptual View

| Legend Box                  | Value                                                |
|-----------------------------|------------------------------------------------------|
| **Architecture Domain**     | Application                                          |
| **Blueprint Type**          | Component Relationship Diagram                       |
| **Scope**                   | Project                                              |
| **Level of Abstraction**    | Conceptual                                           |
| **State**                   | To-Be                                                |
| **Communication Objective** | Bounded components and the responsibilities each one owns |
| **Authors**                 | QuantIAN Team                                        |
| **Revision Date**           | 2026-04-21                                           |
| **Status**                  | Working Draft                                        |

## Diagram

```mermaid
flowchart TB
  subgraph IOT_LAYER["🌐 IoT Layer"]
    direction LR
    SENSOR["Market Sensor Simulator<br/><small>price + volume random walk<br/>anomaly injection</small>"]
    BROKER["MQTT Broker<br/><small>topics: quantian/market/&lt;class&gt;/&lt;symbol&gt;</small>"]
    SENSOR --> BROKER
  end

  subgraph P2P_FOUND["🔗 P2P / Audit Foundation"]
    direction LR
    REG["Peer Registry<br/><small>register · heartbeat · capabilities</small>"]
    DISC["Capability Discovery<br/><small>GET /registry/capabilities/{cap}</small>"]
    LEDGER["Hash-Chained Ledger<br/><small>append-only · SHA-256 · auto-verified</small>"]
    REG --- DISC
    REG --- LEDGER
  end

  subgraph APP_LAYER["⚙️ Application Layer"]
    direction LR
    INGESTOR["Ingestion Peer<br/><small>MarketSensorMessage → MarketEvent</small>"]
    ML["Anomaly Detection<br/><small>rule + Isolation Forest</small>"]
    RISK_CALC["Risk Analytics<br/><small>vol · VaR · max DD · 1d return</small>"]
    REVIEW["Human Review<br/><small>confirm · false+ · dismiss</small>"]
    INGESTOR --> ML
    INGESTOR --> RISK_CALC
    ML <--> REVIEW
  end

  subgraph PRESENT["🖥️ Presentation Layer"]
    direction LR
    STREAMLIT["Streamlit Dashboard<br/><small>operator view</small>"]
    REACT["React Dashboard<br/><small>industrial ops console</small>"]
  end

  subgraph PAAS["☁️ Cloud PaaS Layer"]
    direction LR
    AWSP["AWS<br/><small>EC2 · IoT Core · Elastic IP</small>"]
    AZURE_P["Azure<br/><small>Container Apps · Blob Storage · ACR</small>"]
    GCP_P["GCP<br/><small>Compute Engine · Firewall rule</small>"]
  end

  IOT_LAYER --> APP_LAYER
  APP_LAYER --> P2P_FOUND
  APP_LAYER --> PRESENT
  APP_LAYER --> PAAS
  PRESENT --> P2P_FOUND

  classDef iot    fill:#38BDF822,stroke:#38BDF8,color:#38BDF8;
  classDef p2p    fill:#A78BFA22,stroke:#A78BFA,color:#A78BFA;
  classDef app    fill:#10B98122,stroke:#10B981,color:#10B981;
  classDef ui     fill:#F59E0B22,stroke:#F59E0B,color:#F59E0B;
  classDef paas   fill:#F43F5E22,stroke:#F43F5E,color:#F43F5E;
  class IOT_LAYER iot
  class P2P_FOUND p2p
  class APP_LAYER app
  class PRESENT ui
  class PAAS paas
```

## Bounded components

| Component              | Owns                                                  | Reference |
|------------------------|-------------------------------------------------------|-----------|
| Market Sensor          | synthetic ticks with anomaly injection                | [simulator/mqtt_publisher/](../../simulator/mqtt_publisher/) |
| MQTT Broker            | durable topic bus                                     | Mosquitto (eclipse-mosquitto) |
| Peer Registry          | peers list + capability index + heartbeat TTL        | [registry_service/](../../registry_service/) |
| Capability Discovery   | "who can do X?" lookup                               | [registry_service/main.py](../../registry_service/main.py) |
| Hash-Chained Ledger    | append-only tamper-evident log + auto-verification    | [registry_service/store.py](../../registry_service/store.py) |
| Ingestion Peer         | normalize raw ticks + route by capability             | [aws_ingestion/](../../aws_ingestion/) |
| Anomaly Detection      | rule-based + Isolation Forest scoring                 | [azure_anomaly/service.py](../../azure_anomaly/service.py) |
| Risk Analytics         | portfolio vol / VaR / max drawdown / rolling return   | [gcp_risk/service.py](../../gcp_risk/service.py) |
| Human Review           | alert triage workflow                                 | [azure_anomaly/main.py](../../azure_anomaly/main.py) |
| IoT Bridge             | MQTT → HTTP ingestion adapter                         | [iot/bridge.py](../../iot/bridge.py) |
| Operator Dashboards    | read-only live views over all peers                   | [dashboard/app.py](../../dashboard/app.py), [web_dashboard/](../../web_dashboard/) |
