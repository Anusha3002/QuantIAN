# Blueprint 01 — Presentation View

| Legend Box                  | Value                                              |
|-----------------------------|----------------------------------------------------|
| **Architecture Domain**     | Application                                        |
| **Blueprint Type**          | Executive System Story                             |
| **Scope**                   | Project                                            |
| **Level of Abstraction**    | Presentation                                       |
| **State**                   | To-Be                                              |
| **Communication Objective** | Explain QuantIAN end-to-end in one diagram         |
| **Authors**                 | QuantIAN Team                                      |
| **Revision Date**           | 2026-04-21                                         |
| **Status**                  | Working Draft                                      |

## Narrative (for an evaluator reading this cold)

A simulated sensor publishes market ticks over MQTT. Four independent cloud
services — AWS, Azure, GCP, plus an AWS-resident IoT bridge — find each other
through a shared registry, cooperate on the tick, and record every cross-peer
action on an append-only audit ledger. A dashboard summarizes the whole thing.

## Diagram

```mermaid
flowchart LR
  subgraph IOT["IoT Layer"]
    SIM(["Market Sensor<br/>Simulator"]) -->|MQTT| BROKER[["Mosquitto Broker"]]
  end

  subgraph AWS["AWS"]
    BRIDGE["IoT Bridge<br/>(MQTT → HTTP)"]
    INGEST["Ingestion Peer<br/>(normalize + route)"]
  end

  subgraph AZURE["Azure"]
    ANOMALY["Anomaly Peer<br/>(rule + Isolation Forest)"]
  end

  subgraph GCP["GCP"]
    RISK["Risk Peer<br/>(vol / VaR / DD / 1d)"]
  end

  subgraph SHARED["Shared Control Plane"]
    REGISTRY[("Registry + Ledger<br/>(supernode)")]
  end

  UI["Operator Dashboard<br/>(Streamlit + React)"]

  BROKER -->|subscribe<br/>quantian/market/+/+| BRIDGE
  BRIDGE -->|POST /ingestion/messages| INGEST

  INGEST -.discover by capability.-> REGISTRY
  ANOMALY -.register + heartbeat.-> REGISTRY
  RISK -.register + heartbeat.-> REGISTRY
  BRIDGE -.register.-> REGISTRY

  INGEST -->|MarketEvent| ANOMALY
  INGEST -->|MarketEvent| RISK
  INGEST -->|POST /risk/compute| RISK

  ANOMALY -.ledger block.-> REGISTRY
  RISK    -.ledger block.-> REGISTRY
  INGEST  -.ledger block.-> REGISTRY

  REGISTRY --> UI
  ANOMALY --> UI
  RISK --> UI
  BRIDGE --> UI

  classDef aws    fill:#F59E0B22,stroke:#F59E0B,color:#F59E0B;
  classDef azure  fill:#38BDF822,stroke:#38BDF8,color:#38BDF8;
  classDef gcp    fill:#10B98122,stroke:#10B981,color:#10B981;
  classDef shared fill:#A78BFA22,stroke:#A78BFA,color:#A78BFA;
  class AWS aws
  class AZURE azure
  class GCP gcp
  class SHARED shared
```

## What the evaluator should take away

1. **Four required course pillars** are visible on this single diagram:
   Multi-cloud PaaS (AWS / Azure / GCP), ML (anomaly peer), IoT (MQTT sensor
   stream), P2P + blockchain (registry + audit ledger).
2. **No service talks to another by hardcoded URL.** The dotted lines to the
   registry represent the runtime discovery that enables every solid arrow.
3. **Every solid arrow also leaves a footprint on the ledger.** That's what
   makes QuantIAN's audit story real rather than theatrical.
