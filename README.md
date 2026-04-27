# QuantIAN — Multi-Cloud Intelligent Autonomous Network for Quantitative Market Analytics

QuantIAN is a fully deployed, three-cloud distributed system that ingests live market data, detects anomalies using machine learning, and computes portfolio risk metrics — all connected via a peer-to-peer overlay network with a hash-chained event ledger.

> **Live deployment** — the system is running across AWS, Azure, and GCP.  
> Dashboard: `http://3.217.147.34:8501`

---

## Architecture

```
                        ┌─────────────────────────────┐
                        │     P2P Registry Supernode   │
                        │  (hash-chained ledger + peer  │
                        │   discovery + heartbeats)     │
                        │     AWS EC2 · port 8000       │
                        └───────────┬──────────────────┘
                                    │  all peers register here
              ┌─────────────────────┼──────────────────────┐
              │                     │                       │
   ┌──────────▼──────────┐ ┌───────▼────────┐  ┌──────────▼──────────┐
   │   AWS Ingestion      │ │ Azure Anomaly  │  │    GCP Risk          │
   │   FastAPI · :8001    │ │ FastAPI · :8002│  │  FastAPI · :8003     │
   │   AWS EC2            │ │ Azure Container│  │   GCP VM             │
   │                      │ │ Apps           │  │                      │
   │ • Receives market    │ │ • Isolation    │  │ • Portfolio VaR      │
   │   events via HTTP    │ │   Forest ML    │  │ • Volatility         │
   │   + MQTT IoT bridge  │ │ • Anomaly      │  │ • Max drawdown       │
   │ • Routes events to   │ │   alerts       │  │ • Rolling return     │
   │   all peers via      │ │ • Azure Blob   │  │ • Risk snapshots     │
   │   capability lookup  │ │   state store  │  │                      │
   └──────────────────────┘ └───────────────-┘  └─────────────────────┘
              ▲
              │
   ┌──────────┴──────────┐
   │    IoT MQTT Bridge   │         ┌─────────────────────────┐
   │    (paho-mqtt)       │◄────────│  Live Market Data Feed   │
   │    port 8004         │         │  scripts/live_market_    │
   │                      │         │  feed.py (Yahoo Finance) │
   │  Subscribes to MQTT  │         │  AAPL · MSFT · NVDA ·   │
   │  broker, forwards to │         │  TSLA · BTC · ETH ·     │
   │  ingestion peer      │         │  Gold · Oil · ...        │
   └──────────────────────┘         └─────────────────────────┘
```

### How the P2P layer works

Every service registers itself with the registry supernode at startup, announcing its cloud, address, and capabilities (e.g. `"detect_anomalies"`, `"compute_risk"`, `"ingest_market_data"`). Peers are never hard-coded — routing is always resolved at runtime by querying `GET /registry/capabilities/{capability}`. A background heartbeat loop marks peers ONLINE → STALE (90s) → OFFLINE (180s). Failed routes are retried with exponential backoff and recorded as blocks in the ledger.

The registry maintains a **hash-chained ledger**: every market event, routing attempt, anomaly alert, and heartbeat is appended as a block whose hash includes the previous block's hash (SHA-256), forming an immutable audit trail. The ledger is automatically verified every 60 seconds.

---

## Live Deployment

| Service | Cloud | Address |
|---|---|---|
| P2P Registry | AWS EC2 (`us-east-1`) | `http://3.217.147.34:8000` |
| Market Data Ingestion | AWS EC2 (`us-east-1`) | `http://3.217.147.34:8001` |
| Streamlit Dashboard | AWS EC2 (`us-east-1`) | `http://3.217.147.34:8501` |
| Anomaly Detection | Azure Container Apps (`eastus`) | `https://quantian-azure-anomaly.yellowocean-36a09ba3.eastus.azurecontainerapps.io` |
| Risk Analysis | GCP VM (`us-central1`) | `http://35.192.123.119:8003` |

All three cloud nodes are registered with the P2P registry and actively processing events. The ledger has recorded **79,000+ blocks**.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Services | Python 3.11 · FastAPI · Uvicorn |
| ML (anomaly detection) | scikit-learn Isolation Forest |
| IoT | MQTT (Eclipse Mosquitto) · paho-mqtt |
| Live data feed | yfinance (Yahoo Finance) |
| State / persistence | JSON file store · Azure Blob Storage (anomaly node) |
| Dashboard | Streamlit · React + TypeScript + Vite |
| Containerisation | Docker · docker-compose |
| CI | GitHub Actions |
| Clouds | AWS EC2 · Azure Container Apps · GCP Compute Engine |

---

## Repository Structure

```
QuantIAN/
├── aws_ingestion/          # AWS node — market data ingestion + event routing
├── azure_anomaly/          # Azure node — ML anomaly detection (Isolation Forest)
├── gcp_risk/               # GCP node — portfolio risk analysis (VaR, volatility)
├── registry_service/       # P2P supernode — peer registry + hash-chained ledger
├── iot/                    # IoT bridge — MQTT subscriber → ingestion peer
├── shared/                 # Shared schemas, ServiceRuntime, config, utils
│   ├── schemas/            #   Pydantic models (MarketEvent, AnomalyAlert, …)
│   ├── runtime/            #   ServiceRuntime: register, heartbeat, route_with_retries
│   └── config/             #   Environment-based settings loader
├── simulator/              # MQTT publisher for local testing
│   └── mqtt_publisher/
├── scripts/
│   ├── live_market_feed.py # Live Yahoo Finance → ingestion feed (run for demo)
│   ├── local_flow_demo.py  # End-to-end local smoke test
│   ├── service_smoke_test.py
│   └── start_quantian.sh
├── web_dashboard/          # React/TypeScript dashboard (Alerts, Peers, Ledger, Risk…)
├── dashboard/              # Streamlit dashboard
├── infra/                  # VM bootstrap scripts, Mosquitto config
├── dist/                   # Deployment artefacts (live endpoint configs)
├── docs/                   # Architecture docs, P2P overlay spec, screenshots
│   ├── P2P_OVERLAY.md
│   ├── MASTER_TECHNICAL_DOCUMENT.md
│   └── LIVE_IMPLEMENTATION_TECHNICAL_DOCUMENT.md
├── tests/                  # Unit tests
│   ├── test_ledger_chain.py
│   ├── test_routing_retries.py
│   ├── test_anomaly_scoring.py
│   ├── test_risk_math.py
│   └── test_mqtt_bridge.py
├── docker-compose.yml
├── Dockerfile
└── requirements.txt
```

---

## Running Locally

### Prerequisites
- Docker + Docker Compose
- Python 3.11+

### Start the full stack

```bash
# Build and start all services (registry, ingestion, anomaly, risk, IoT bridge)
docker compose up --build

# Include the dashboards
docker compose --profile ui up --build
```

Services will be available at:

| Service | URL |
|---|---|
| Registry | `http://localhost:8000` |
| Ingestion | `http://localhost:8001` |
| Anomaly | `http://localhost:8002` |
| Risk | `http://localhost:8003` |
| IoT Bridge | `http://localhost:8004` |
| Streamlit Dashboard | `http://localhost:8501` |
| React Dashboard | `http://localhost:5174` |

### Feed live market data

```bash
# Install dependencies
pip3 install yfinance requests

# Start the live feed (fetches real prices every 60s and posts to ingestion)
python3 scripts/live_market_feed.py

# Options
python3 scripts/live_market_feed.py --endpoint http://localhost:8001   # point at local stack
python3 scripts/live_market_feed.py --interval 30                      # faster refresh
python3 scripts/live_market_feed.py --symbols AAPL MSFT BTC-USD        # specific tickers only
python3 scripts/live_market_feed.py --once                             # one cycle then exit
```

### Run the MQTT simulator (alternative to live feed)

```bash
python3 -m simulator.mqtt_publisher.cli --cycles 20 --interval 5
```

### Run tests

```bash
pip3 install -r requirements.txt
pytest tests/ -v
```

---

## API Reference

### Registry (`/registry/*`, `/ledger/*`)

| Method | Path | Description |
|---|---|---|
| `POST` | `/registry/peers` | Register a peer |
| `POST` | `/registry/peers/{id}/heartbeat` | Send heartbeat |
| `GET` | `/registry/peers` | List all peers with status |
| `GET` | `/registry/capabilities/{cap}` | Discover peers by capability |
| `POST` | `/ledger/blocks` | Append a ledger block |
| `GET` | `/ledger/blocks` | Read the full ledger |
| `GET` | `/ledger/verify` | Verify chain integrity |

### Ingestion (`/ingestion/*`)

| Method | Path | Description |
|---|---|---|
| `POST` | `/ingestion/messages` | Ingest a raw market sensor message |
| `POST` | `/ingestion/events` | Ingest a pre-normalised market event |
| `GET` | `/ingestion/events/recent` | Get the last 20 events |

### Anomaly (`/anomaly/*`)

| Method | Path | Description |
|---|---|---|
| `POST` | `/anomaly/analyze` | Score a market event for anomalies |
| `GET` | `/anomaly/alerts` | List all anomaly alerts |
| `PUT` | `/anomaly/alerts/{id}/review` | Human-in-the-loop alert review |

### Risk (`/risk/*`)

| Method | Path | Description |
|---|---|---|
| `POST` | `/risk/compute` | Compute a risk snapshot for the current portfolio |
| `GET` | `/risk/latest` | Get the most recent risk snapshot |
| `GET` | `/risk/history` | Get all historical risk snapshots |
| `GET`/`POST` | `/risk/portfolio` | Read or update the portfolio |

---

## Course Requirement Coverage

| Requirement | Implementation |
|---|---|
| ≥ 2 cloud vendors | AWS EC2 · Azure Container Apps · GCP VM — all three live |
| PaaS — IoT | Eclipse Mosquitto MQTT broker + paho-mqtt IoT bridge (port 8004) |
| PaaS — Machine Learning | scikit-learn Isolation Forest anomaly detection, running on Azure |
| PaaS — P2P overlay | Supernode registry with dynamic capability discovery + heartbeat lifecycle |
| Blockchain / ledger | Hash-chained append-only ledger (SHA-256), auto-verified every 60s |
| Multi-cloud integration | Events routed across all 3 clouds in real time via P2P capability lookup |
| Live market data | Yahoo Finance live feed via `scripts/live_market_feed.py` |

---

## Team

| Member | Ownership |
|---|---|
| **Anusha** | AWS ingestion node · P2P overlay layer · Live market data feed · ADF migration analysis |
| **Aditi** | Azure anomaly detection · Web dashboard |
| **Bhavesh** | GCP risk analysis · Full-stack implementation · Cloud deployment |
