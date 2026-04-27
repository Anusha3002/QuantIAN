# QuantIAN Master Technical Document

Status: Draft v1
Date: 2026-04-20
Project: QuantIAN - Multi-Cloud Intelligent Autonomous Network for Quantitative Market Analytics

## 1. Purpose

This document is the implementation baseline for QuantIAN. It consolidates:

- the current MVP plan in `QuantIAN_MVP_Plan.docx`
- the assignment guidance summarized in the working conversation
- the professor's apparent requirement that the project demonstrate four pillars:
  - multi-cloud / PaaS
  - machine learning
  - IoT
  - P2P / blockchain

The goal is to remove ambiguity before coding. This document defines what we are building, why we are building it this way, the features that are in scope, the architecture we will implement, the data contracts between services, and the order of execution for the engineering work.

## 2. Source Note

This document is based on:

- direct extraction from `QuantIAN_MVP_Plan.docx`
- direct review of `/Users/bhaveshgupta01/oS/CC/ProjectIdeas.pdf`
- direct review of `/Users/bhaveshgupta01/oS/CC/ArchitectureBlueprinting.pdf`

The PDF review confirms two implementation-shaping requirements:

- `ProjectIdeas.pdf` explicitly frames the project as an application built on top of an underlying framework and P2P network.
- `ArchitectureBlueprinting.pdf` explicitly expects blueprint discipline around domain, scope, abstraction, and state, with a legend box on every blueprint.

## 3. Final Decision

QuantIAN will **not** be implemented as only three cloud services connected by hardcoded REST calls.

QuantIAN **will** be implemented as a lightweight multi-cloud P2P analytics framework with a cloud-backed bootstrap registry and an append-only audit ledger. The analytics application sits on top of that foundation.

### 3.1 Required Pillars and How We Satisfy Them

| Pillar | Required | QuantIAN implementation |
| --- | --- | --- |
| Multi-cloud / PaaS | Yes | AWS + Azure + GCP, each owning a distinct service role |
| Machine Learning | Yes | Isolation Forest based anomaly detection with feedback-aware thresholds |
| IoT | Yes | MQTT-based simulated market data sensor stream via AWS IoT Core or local MQTT-compatible simulator |
| P2P / Blockchain | Yes | Peer registry + discovery + heartbeat + direct peer messaging + append-only hash-chained audit ledger |

### 3.2 Design Principle

The professor's requirement is best interpreted as:

1. Build a lightweight P2P framework / overlay first.
2. Run the domain application on top of it.
3. Show multi-cloud deployment and cloud PaaS usage clearly.
4. Document the architecture in multiple views, not just code.

That means the foundation is:

- peer registration
- capability advertisement
- heartbeat tracking
- service discovery
- cross-peer event exchange
- auditability of peer actions

The application layer is:

- market data ingestion
- anomaly detection
- human review
- portfolio risk analytics
- dashboard visualization

## 4. Product Definition

QuantIAN is a distributed market analytics platform that ingests market data, detects anomalous behavior, computes portfolio risk metrics, and presents results in a dashboard. The system runs across AWS, Azure, and GCP as cooperating peers in a logical P2P overlay network.

## 5. Scope

### 5.1 In Scope for MVP

- Peer bootstrap registry
- Peer heartbeat and status tracking
- Peer capability discovery
- Direct peer-to-peer service invocation through discovered endpoints
- MQTT market data ingestion from a simulated IoT data source
- Market event normalization
- Historical event persistence
- Isolation Forest anomaly detection
- Anomaly alert creation
- Human-in-the-loop alert review
- Portfolio risk metric computation
- Dashboard showing live feed, peer health, alerts, and risk
- Append-only audit ledger for cross-node actions
- Multi-cloud deployment mapping for AWS, Azure, and GCP
- Architecture blueprints for presentation and reporting

### 5.2 Out of Scope for MVP

- Full custom decentralized DHT or Kademlia-style overlay
- Real trading execution
- Brokerage integration
- High-frequency low-latency processing
- Deep learning models
- Smart contract deployment on public chains
- Native mobile application
- Full self-healing orchestration
- Real market-grade event throughput

## 6. Core Use Cases

| ID | Use case | Expected demo proof |
| --- | --- | --- |
| UC1 | Peer joins the QuantIAN network | Dashboard shows a new peer registered with capabilities and heartbeat |
| UC2 | IoT market sensor publishes data | Market events appear in the live feed and raw event store |
| UC3 | AWS ingestion peer normalizes and republishes event | Event reaches downstream peers through discovery-driven routing |
| UC4 | Azure anomaly peer flags suspicious movement | Alert appears in dashboard with score, reason, and state |
| UC5 | Human reviews alert | Alert state changes to approved or false positive |
| UC6 | GCP risk peer recomputes portfolio metrics | Dashboard shows volatility, VaR, drawdown, and timestamp |
| UC7 | Audit ledger records cross-peer actions | Dashboard or API shows hash-linked event history |
| UC8 | Multi-cloud architecture is visible | AWS, Azure, and GCP service roles can be shown side by side |

## 7. Architecture Overview

### 7.1 High-Level Stack

```text
+---------------------------------------------------------------+
| Dashboard / API Gateway                                       |
| Streamlit UI + lightweight backend aggregation endpoints       |
+---------------------------------------------------------------+
| QuantIAN Application Services                                 |
| AWS Ingestion Peer | Azure Anomaly Peer | GCP Risk Peer       |
+---------------------------------------------------------------+
| QuantIAN P2P Foundation                                       |
| Peer Registry | Discovery | Heartbeats | Event Routing        |
| Append-Only Audit Ledger                                      |
+---------------------------------------------------------------+
| IoT Layer                                                     |
| MQTT Market Sensor Simulator                                  |
+---------------------------------------------------------------+
| Cloud PaaS Layer                                               |
| AWS services | Azure services | GCP services                  |
+---------------------------------------------------------------+
```

### 7.2 Logical View

```text
MQTT Sensor --> AWS Ingestion Peer --> Shared Event Store --> Azure Anomaly Peer
       |                 |                    |                    |
       |                 +--> Audit Ledger <--+--> Audit Ledger <--+
       |                                      |
       +--------------> Peer Registry <-------+
                                              |
                                              v
                                      GCP Risk Peer
                                              |
                                              v
                                         Dashboard
```

### 7.3 Final Implementation Model

- The P2P overlay is **lightweight**, not fully decentralized.
- A bootstrap supernode pattern is acceptable and aligns with past project precedent.
- The registry is used for discovery and liveness.
- After discovery, peers communicate directly through HTTP APIs and event publication.
- The ledger gives the project a blockchain-style audit story without forcing Ethereum or smart contracts into the MVP.

## 8. Architecture Views Required for Course Deliverables

The PDF confirms that architecture artifacts should be described by:

- architecture domain
- scope
- level of abstraction
- state
- communication objective

The PDF also defines four abstraction levels: presentation, conceptual, logical, and physical.

For QuantIAN, we should prepare at least the following views with a legend box on each:

### 8.1 Presentation / Executive View

- Audience: professor and evaluators
- Purpose: explain what QuantIAN does in one diagram
- Focus: users, peers, major flows, major clouds

### 8.2 Conceptual View

- Audience: system design discussion
- Purpose: show the major bounded components and relationships
- Focus: dashboard, P2P layer, IoT input, ML, risk, ledger

### 8.3 Logical View

- Audience: engineering
- Purpose: show services, APIs, topics, storage, and interactions
- Focus: endpoints, topics, schemas, event flow

### 8.4 Physical / Deployment View

- Audience: implementation and demo
- Purpose: show which service runs on which cloud and which PaaS services are used
- Focus: AWS, Azure, GCP resources and network edges

### 8.5 Standard Legend Box Template

Each blueprint should include:

- Architecture Domain: Business / Application / Data / Technical
- Scope: Project
- Abstraction: Presentation / Conceptual / Logical / Physical
- State: To-Be
- Authors: team members
- Date: current revision date
- Blueprint Type: the specific diagram type being shown
- Status: Working Draft or Final

### 8.6 Recommended QuantIAN Blueprint Matrix

| Domain | Presentation | Conceptual | Logical | Physical |
| --- | --- | --- | --- | --- |
| Business | optional | project goals, actors, review workflow | optional | optional |
| Application | system story | service map | APIs, topics, service interactions | deployed applications by cloud |
| Data | optional | major data objects | event, alert, risk, ledger schemas and data flow | storage placement by cloud |
| Technical | cloud summary | infra capabilities | registry, MQTT, networking, adapters | concrete AWS, Azure, GCP resources |

## 9. Chosen Technical Stack

### 9.1 Language and App Stack

- Python for all backend services
- FastAPI for peer services and shared APIs
- Streamlit for the MVP dashboard
- scikit-learn for anomaly detection
- pandas / numpy for analytics
- Pydantic for request and event schemas

### 9.2 Cloud / Service Mapping

| Cloud | Peer role | Primary service choices |
| --- | --- | --- |
| AWS | Registry + ingestion peer + dashboard host | Ubuntu EC2 VM, Elastic IP, security group, optional AWS IoT Core adapter |
| Azure | Anomaly detection peer | Azure Container Apps for FastAPI + Azure Blob Storage for durable anomaly state |
| GCP | Risk analytics peer | Ubuntu Compute Engine VM, firewall rule, systemd service |

### 9.3 Why This Stack

- Python reduces team fragmentation.
- FastAPI keeps local development and cloud deployment simple.
- Streamlit is the fastest path to a credible analytics dashboard.
- A hybrid rollout keeps AWS and GCP operationally simple on VMs while avoiding Azure VM quota blockers through Container Apps.
- Managed services remain optional future extensions once the VM deployment path is stable.

## 10. P2P Foundation Design

### 10.1 Peer Types

The system starts with four logical node types:

- `registry`: bootstrap and discovery service
- `ingestion`: AWS market ingestion peer
- `anomaly`: Azure anomaly detection peer
- `risk`: GCP risk computation peer

Later additions can include:

- `dashboard`
- `review`
- `notifier`

### 10.2 Peer Registration

Every peer registers itself at startup.

Required fields:

```json
{
  "node_id": "azure-anomaly-01",
  "node_type": "anomaly",
  "cloud": "azure",
  "base_url": "https://example.azurewebsites.net",
  "capabilities": [
    "detect_anomalies",
    "list_alerts",
    "submit_review_feedback"
  ],
  "status": "online",
  "last_heartbeat": "2026-04-20T13:00:00Z",
  "metadata": {
    "version": "0.1.0",
    "region": "eastus"
  }
}
```

### 10.3 Heartbeat Model

- Each peer sends a heartbeat every 20 to 30 seconds.
- A peer is marked `stale` if no heartbeat is seen within 90 seconds.
- A peer is marked `offline` if no heartbeat is seen within 180 seconds.
- The dashboard must expose peer health clearly.

### 10.4 Capability Discovery

Peers will query the registry by capability, not by hardcoded URL.

Example:

- AWS peer asks registry: who supports `detect_anomalies`?
- Registry returns the Azure anomaly peer endpoint.
- AWS peer forwards normalized event payload to that peer.

### 10.5 Direct Peer Communication

Direct peer communication will use:

- HTTP POST for event delivery
- HTTP GET for pull-based retrieval where needed
- optional internal webhook callbacks for notification updates

This is sufficient to defend the system as a lightweight P2P overlay:

- peers join dynamically
- peers advertise capabilities
- peers discover each other at runtime
- peers communicate directly once discovered

## 11. IoT Layer Design

### 11.1 Why IoT Exists in This Project

The project needs an explicit IoT pillar. We will treat market data as a sensor stream instead of a traditional batch API pull only.

### 11.2 IoT Model

- A `market-sensor-simulator` publishes price updates to MQTT topics.
- Topics are structured by asset class and symbol.
- The AWS ingestion peer subscribes to those topics and converts raw messages into normalized market events.

### 11.3 Topic Design

```text
quantian/market/crypto/BTCUSD
quantian/market/crypto/ETHUSD
quantian/market/equity/AAPL
quantian/market/equity/MSFT
```

### 11.4 MQTT Message Schema

```json
{
  "sensor_id": "sensor-coingecko-btc",
  "symbol": "BTCUSD",
  "asset_class": "crypto",
  "price": 68412.55,
  "volume": 123456.78,
  "source": "coingecko",
  "event_time": "2026-04-20T13:01:30Z"
}
```

### 11.5 Implementation Choice

Primary path:

- AWS IoT Core as MQTT broker
- Python publisher process as sensor simulator
- AWS ingestion service subscribes and normalizes messages

Fallback local-development path:

- local MQTT-compatible broker or test publisher stub
- same schema and topic contract

## 12. Ingestion Peer Design (AWS)

### 12.1 Responsibilities

- subscribe to MQTT market topics
- normalize raw sensor data
- persist raw and normalized events
- publish event records to downstream peers
- write ledger entries
- expose recent event APIs

### 12.2 AWS Services

- AWS IoT Core for MQTT ingress
- S3 for raw event archival
- DynamoDB for peer registry and possibly ledger
- Lambda or FastAPI service for normalization and routing

### 12.3 Output Event Schema

```json
{
  "event_id": "evt_01",
  "symbol": "BTCUSD",
  "asset_class": "crypto",
  "price": 68412.55,
  "volume": 123456.78,
  "source": "aws-ingestion",
  "ingested_at": "2026-04-20T13:01:31Z",
  "window": {
    "price_change_1m": 0.018,
    "volume_change_1m": 0.122
  }
}
```

### 12.4 Required APIs

- `POST /register`
- `POST /heartbeat`
- `GET /events/recent`
- `POST /events/publish`
- `GET /health`

## 13. Anomaly Peer Design (Azure)

### 13.1 Responsibilities

- receive normalized market events
- maintain feature pipeline
- score events with Isolation Forest
- create alerts when threshold is crossed
- accept human review feedback
- expose current and historical alert APIs
- write ledger entries

### 13.2 Model Strategy

Primary model:

- Isolation Forest over rolling-window derived features

Example features:

- price delta over 1 minute
- price delta over 5 minutes
- volume delta over 1 minute
- rolling z-score
- volatility spike

Cold-start fallback:

- simple statistical thresholding until sufficient history exists

### 13.3 Alert Schema

```json
{
  "alert_id": "alt_01",
  "event_id": "evt_01",
  "symbol": "BTCUSD",
  "severity": "high",
  "score": 0.94,
  "reason": "price spike with volume surge",
  "status": "pending_review",
  "created_at": "2026-04-20T13:01:34Z"
}
```

### 13.4 Review States

- `pending_review`
- `confirmed`
- `false_positive`
- `dismissed`

### 13.5 Required APIs

- `POST /events/analyze`
- `GET /alerts`
- `GET /alerts/{alert_id}`
- `POST /alerts/{alert_id}/review`
- `GET /health`

## 14. Risk Peer Design (GCP)

### 14.1 Responsibilities

- consume accumulated normalized market data
- compute portfolio analytics
- persist metric snapshots
- expose latest and historical risk metrics
- write ledger entries

### 14.2 Metrics in MVP

- annualized volatility
- Value at Risk (historical or parametric)
- max drawdown
- rolling return
- portfolio exposure summary

### 14.3 Input Portfolio Model

```json
{
  "portfolio_id": "demo_portfolio",
  "positions": [
    { "symbol": "BTCUSD", "weight": 0.4 },
    { "symbol": "ETHUSD", "weight": 0.3 },
    { "symbol": "AAPL", "weight": 0.2 },
    { "symbol": "MSFT", "weight": 0.1 }
  ]
}
```

### 14.4 Risk Snapshot Schema

```json
{
  "snapshot_id": "risk_01",
  "portfolio_id": "demo_portfolio",
  "as_of": "2026-04-20T13:05:00Z",
  "volatility": 0.27,
  "value_at_risk_95": -0.034,
  "max_drawdown": -0.11,
  "rolling_return_1d": 0.014
}
```

### 14.5 Required APIs

- `POST /risk/compute`
- `GET /risk/latest`
- `GET /risk/history`
- `GET /health`

## 15. Append-Only Audit Ledger Design

### 15.1 Why We Need It

The assignment appears to expect a blockchain or blockchain-like component. A lightweight audit ledger is the right MVP interpretation for a finance-oriented system.

### 15.2 Ledger Model

Each important cross-peer action is recorded as a hash-linked block:

- peer registered
- heartbeat processed
- event ingested
- event forwarded
- anomaly alert created
- alert reviewed
- risk snapshot computed

### 15.3 Block Schema

```json
{
  "block_id": 21,
  "timestamp": "2026-04-20T13:01:34Z",
  "event_type": "alert_created",
  "actor_node": "azure-anomaly-01",
  "payload_hash": "sha256:...",
  "previous_hash": "sha256:...",
  "block_hash": "sha256:..."
}
```

### 15.4 Implementation Choice

- Logical blockchain, not cryptocurrency
- Hash chaining implemented in application code
- Storage in DynamoDB or S3-backed append log
- Ledger verification endpoint recomputes and confirms chain integrity

### 15.5 Required APIs

- `POST /ledger/append`
- `GET /ledger/blocks`
- `GET /ledger/verify`

## 16. Dashboard Design

### 16.1 MVP Dashboard Choice

Use Streamlit for MVP speed. The dashboard is not the grading centerpiece; the distributed architecture is.

### 16.2 Dashboard Pages

- Overview
- Live Market Feed
- Peer Registry / Network Health
- Anomaly Alerts
- Risk Metrics
- Audit Ledger

### 16.3 Widgets / Sections

Overview:

- system summary cards
- active peers
- latest alert count
- latest risk snapshot

Live Market Feed:

- latest normalized events table
- price sparkline or trend view

Peer Registry:

- peer table with status, cloud, capabilities, heartbeat age

Alerts:

- alert table
- severity filter
- review action buttons

Risk:

- volatility card
- VaR card
- max drawdown card
- history chart

Ledger:

- recent block list
- chain verification status

## 17. Data Storage Plan

| Data type | Storage | Reason |
| --- | --- | --- |
| Raw MQTT payloads | S3 | cheap archival and demo evidence |
| Peer registry | DynamoDB | simple key-value / document access |
| Normalized market events | S3 or local dev JSON/SQLite, later BigQuery export | MVP simplicity with analytics path |
| Alerts | Azure-side storage or shared document store | easy alert retrieval |
| Risk snapshots | BigQuery or local dev table mirrored to GCP | analytics-friendly |
| Audit ledger | DynamoDB or append-only JSON log in S3 | tamper-evident chain |

## 18. Service Contracts

### 18.1 Registry Endpoints

- `POST /registry/peers`
- `POST /registry/peers/{node_id}/heartbeat`
- `GET /registry/peers`
- `GET /registry/capabilities/{capability}`
- `GET /registry/health`

### 18.2 Ingestion Endpoints

- `POST /ingestion/events`
- `GET /ingestion/events/recent`
- `GET /ingestion/health`

### 18.3 Anomaly Endpoints

- `POST /anomaly/analyze`
- `GET /anomaly/alerts`
- `POST /anomaly/alerts/{alert_id}/review`
- `GET /anomaly/health`

### 18.4 Risk Endpoints

- `POST /risk/compute`
- `GET /risk/latest`
- `GET /risk/history`
- `GET /risk/health`

### 18.5 Ledger Endpoints

- `POST /ledger/blocks`
- `GET /ledger/blocks`
- `GET /ledger/verify`

## 19. Suggested Repository Structure

```text
CrossCloudAnalyser/
  docs/
    MASTER_TECHNICAL_DOCUMENT.md
    diagrams/
      conceptual-view.drawio
      logical-view.drawio
      physical-view.drawio
  shared/
    schemas/
    utils/
    config/
  registry_service/
  aws_ingestion/
  azure_anomaly/
  gcp_risk/
  dashboard/
  simulator/
    mqtt_publisher/
  infra/
    aws/
    azure/
    gcp/
  scripts/
  README.md
```

## 20. Implementation Order

### Phase 1: Shared Contracts and Local Skeleton

1. Create repo structure.
2. Add shared Pydantic schemas.
3. Create local `.env` contract and config loader.
4. Implement the registry service first.

### Phase 2: P2P Foundation

1. Implement peer registration and heartbeat.
2. Implement capability lookup.
3. Implement ledger append and verification.
4. Add health endpoints.

### Phase 3: Market Simulation and Ingestion

1. Build MQTT market sensor simulator.
2. Build AWS ingestion peer subscriber / receiver.
3. Normalize and persist events.
4. Route events to anomaly peer through registry discovery.

### Phase 4: Anomaly Detection

1. Implement rolling feature engineering.
2. Add Isolation Forest scoring.
3. Create alert persistence and list APIs.
4. Add alert review endpoint.

### Phase 5: Risk Engine

1. Implement portfolio schema and seed portfolio.
2. Build risk computation module.
3. Persist and expose snapshots.

### Phase 6: Dashboard

1. Build overview page.
2. Build peer registry page.
3. Build alerts page with review controls.
4. Build risk and ledger pages.

### Phase 7: Cloud Deployment and Presentation Assets

1. Map each service to its cloud environment.
2. Produce conceptual, logical, and physical diagrams.
3. Gather screenshots and demo steps.

## 21. Local Development Strategy

To reduce implementation risk, all services should run locally first with cloud adapters abstracted behind configuration.

Example local mode:

- Registry runs as FastAPI on localhost
- MQTT simulator publishes locally or through stub transport
- Ingestion service consumes sample events
- Anomaly and risk services run locally
- Dashboard aggregates local endpoints

After the local flow works, deploy service-by-service to cloud.

## 22. Configuration Strategy

Every service should support:

- `APP_ENV=local|cloud`
- `SERVICE_PORT`
- `REGISTRY_URL`
- `LEDGER_URL`
- `MQTT_BROKER_URL`
- `STORAGE_BACKEND`
- cloud-specific credentials loaded from env vars

No credentials should be hardcoded in source.

## 23. Testing Strategy

### 23.1 Unit Tests

- schema validation
- anomaly scoring logic
- risk calculation correctness
- ledger hash verification

### 23.2 Integration Tests

- peer registration and heartbeat flow
- event routing through registry discovery
- alert creation from sample anomalous input
- risk computation from seeded data

### 23.3 Demo Validation Tests

- can all peers register?
- can dashboard show peer health?
- can a simulated event trigger an alert?
- can human review update alert state?
- can risk metrics refresh?
- can ledger verify as valid?

## 24. Risks and Mitigations

| Risk | Impact | Mitigation |
| --- | --- | --- |
| PDFs may contain additional constraints | medium | revisit document once original files are available |
| Cloud integration consumes too much time | high | build and validate complete local mode first |
| Isolation Forest may be unstable with low data volume | medium | add threshold fallback during cold start |
| IoT setup may be slower than expected | medium | keep local MQTT-compatible simulator path ready |
| Multi-cloud deployment drift | medium | define shared schemas and health contracts first |
| Team divergence | high | treat this document as the contract of record |

## 25. Immediate Coding Backlog

The first coding sprint should produce:

1. `shared/schemas` for peers, events, alerts, risk snapshots, and ledger blocks
2. `registry_service` with register, heartbeat, lookup, health, and ledger endpoints
3. `simulator/mqtt_publisher` for fake market data
4. `aws_ingestion` stub that receives simulated events and writes normalized events
5. local integration script that proves registry -> ingestion -> anomaly flow

## 26. Open Questions

- Does the team want Streamlit locked for MVP, or only as a fallback behind a later React dashboard?
- Should the registry and ledger both live on AWS for simplicity, or should ledger storage be mirrored?
- Which market data symbols will be used for the final demo?
- Will the human-review feedback actually retrain the model, or only be stored as metadata in MVP?

## 27. Decision Summary

QuantIAN should be built as a **lightweight P2P multi-cloud analytics network**, not just a set of isolated cloud services.

The concrete MVP architecture is:

- MQTT market sensor simulator for the IoT pillar
- AWS ingestion peer for event intake and normalization
- Azure anomaly peer for ML scoring and alerting
- GCP risk peer for portfolio analytics
- registry and heartbeat layer for P2P discovery
- append-only hash-chained ledger for blockchain-style auditability
- Streamlit dashboard for visibility, review, and demo readiness

This is the minimum design that satisfies the academic framing while staying implementable on student time and free-tier constraints.
