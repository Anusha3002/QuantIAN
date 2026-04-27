# QuantIAN Live Implementation Technical Document

Status: Live implementation record  
Date: 2026-04-21  
Project: QuantIAN - Multi-Cloud Intelligent Autonomous Network for Quantitative Market Analytics

Related references:

- `docs/MASTER_TECHNICAL_DOCUMENT.md`
- `infra/vm/DEPLOYMENT_NOTES.md`
- `docs/diagrams/quantian_local_mvp.drawio`
- `docs/diagrams/quantian_final_cloud.drawio`

## 1. Document Purpose

This document is the detailed technical record of what has been implemented, deployed, verified, and documented in QuantIAN as of April 21, 2026.

It complements the master technical document. The master document defines the target architecture and scope. This document records the actual implementation that now exists in the repository and the current live multi-cloud deployment that is reachable through public endpoints.

This document answers four questions:

1. What has been built in code?
2. What is currently live in AWS, Azure, and GCP?
3. What deployment work, pivots, and fixes were required to reach go-live?
4. What technical evidence confirms the system is operating?

## 2. Executive Summary

QuantIAN is now implemented as a working multi-cloud analytics platform with a lightweight peer-to-peer overlay, cloud-hosted services, persistent state, deployment automation, live dashboarding, architecture diagrams, and verification tooling.

The current production-style topology is:

- AWS VM hosting the registry service, ingestion peer, and Streamlit dashboard
- Azure Container Apps hosting the anomaly detection peer
- Azure Blob Storage persisting anomaly alerts and history
- GCP VM hosting the risk analytics peer

The system currently demonstrates the required project pillars in implemented form:

| Pillar | Implemented proof |
| --- | --- |
| Multi-cloud / PaaS | AWS EC2 + Azure Container Apps + Azure Blob Storage + GCP Compute Engine |
| Machine Learning | Isolation Forest-based anomaly detection in the Azure anomaly peer |
| IoT | Simulated market sensor publishing flow and MQTT-compatible simulator package |
| P2P / blockchain-style audit | Peer registry, capability discovery, heartbeats, direct peer routing, append-only hash-chained ledger |

As of April 21, 2026:

- all public services report healthy
- the registry sees three online peers
- the anomaly service is persisting state through Azure Blob Storage
- the risk service has a live portfolio loaded and active snapshot history
- the ledger verifies as valid
- architecture diagram sources have been updated to reflect the final hybrid deployment

## 3. Current Live Deployment State

### 3.1 Live Endpoints

The current live endpoints are:

| Role | Cloud | Hosting model | Public endpoint |
| --- | --- | --- | --- |
| Dashboard | AWS | Streamlit on VM | `http://3.217.147.34:8501` |
| Registry | AWS | FastAPI on VM | `http://3.217.147.34:8000` |
| Ingestion peer | AWS | FastAPI on VM | `http://3.217.147.34:8001` |
| Anomaly peer | Azure | Azure Container Apps | `https://quantian-azure-anomaly.yellowocean-36a09ba3.eastus.azurecontainerapps.io` |
| Risk peer | GCP | FastAPI on VM | `http://35.192.123.119:8003` |

Recorded go-live manifest completion time from `dist/live/status.json`:

- `2026-04-21T05:45:48.553855+00:00`

Independent status verification on April 21, 2026 using `.venv/bin/python scripts/cloud_deploy.py status` showed:

- `registry: true`
- `ingestion: true`
- `dashboard: true`
- `anomaly: true`
- `risk: true`

### 3.2 Live Cloud Resource Inventory

The persisted live manifests under `dist/live/` currently describe the deployed resources below.

#### AWS

| Field | Value |
| --- | --- |
| Instance ID | `i-053e7ea72e9c00e01` |
| Public IP | `3.217.147.34` |
| Elastic IP allocation | `eipalloc-0782d42fe12828197` |
| Security group | `sg-0ebf64ab6b66bd8d5` |
| Key name | `quantian-demo-key-20260420234009` |

#### Azure

| Field | Value |
| --- | --- |
| Resource group | `quantian-rg` |
| Container Apps environment | `quantian-azure-env` |
| Container App | `quantian-azure-anomaly` |
| Region | `eastus` |
| Registry | `qtanacr9fe59f582c.azurecr.io` |
| Image | `qtanacr9fe59f582c.azurecr.io/quantian/azure-anomaly:20260421053208` |
| Latest revision | `quantian-azure-anomaly--0000004` |
| CPU | `0.5` |
| Memory | `1.0Gi` |
| Min replicas | `1` |
| Max replicas | `1` |
| Storage account | `qtanom9fe59f582c` |
| Blob container | `quantian-state` |
| Storage backend | `azure_blob` |

#### GCP

| Field | Value |
| --- | --- |
| Project | `nyu-clopud-hw2` |
| Zone | `us-central1-a` |
| Instance | `quantian-gcp-risk` |
| Public IP | `35.192.123.119` |

### 3.3 Live Runtime Evidence

Direct health queries on April 21, 2026 showed:

- Registry health: `{"status":"ok","service":"registry_service","peers":3,"ledger_blocks":354,"peer_counts":{"online":3,"stale":0,"offline":0}}`
- AWS ingestion health: `{"status":"ok","service":"aws_ingestion","node_id":"aws-ingestion-01","raw_messages":16,"normalized_events":16,"forwarded_events":16,"routing_failures":0,"base_url":"http://3.217.147.34:8001"}`
- Azure anomaly health: `{"status":"ok","service":"azure_anomaly","node_id":"azure-anomaly-01","alerts":5,"tracked_symbols":4,"sklearn_enabled":true,"storage_backend":"AzureBlobJsonStateStore","base_url":"https://quantian-azure-anomaly.yellowocean-36a09ba3.eastus.azurecontainerapps.io"}`
- GCP risk health: `{"status":"ok","service":"gcp_risk","node_id":"gcp-risk-01","symbols_tracked":4,"portfolio_loaded":true,"snapshots":33,"base_url":"http://35.192.123.119:8003"}`

The registry peer list showed all three cross-cloud peers online:

- `aws-ingestion-01`
- `azure-anomaly-01`
- `gcp-risk-01`

Ledger verification on April 21, 2026 returned:

- `{"valid":true,"block_count":355,"error":null}`

The slight difference between the registry health block count and the ledger verification block count is expected during live operation because peer heartbeats continue appending new ledger entries between successive API calls.

## 4. Delivered Architecture

### 4.1 Final Runtime Topology

```text
Market Sensor Simulator / MQTT-compatible publisher
                |
                v
        AWS Ingestion Peer
                |
                +---------------------> Azure Anomaly Peer
                |                         |
                |                         +--> Azure Blob Storage
                |
                +---------------------> GCP Risk Peer
                |
                +---------------------> Registry / Ledger
                                          ^
                                          |
                                       Dashboard
```

### 4.2 Service Ownership by Cloud

| Cloud | Implemented responsibility |
| --- | --- |
| AWS | Registry, heartbeat/discovery ledger, ingestion pipeline, dashboard hosting |
| Azure | Anomaly detection service and durable anomaly state |
| GCP | Portfolio storage, event history, and risk computation |

### 4.3 Peer-to-Peer Overlay Model

The system is not a fully decentralized mesh. It is a lightweight overlay with a bootstrap registry:

- peers self-register at startup
- peers send periodic heartbeats
- peers discover other peers by capability
- business events are routed directly to discovered peer endpoints
- cross-node actions are recorded in an append-only hash-chained ledger

This design satisfies the project requirement for a P2P-style framework without introducing unnecessary complexity such as a DHT or public blockchain dependency.

## 5. Repository Implementation Map

| Path | Purpose |
| --- | --- |
| `registry_service/` | Registry APIs, peer tracking, ledger logic |
| `aws_ingestion/` | Ingestion peer APIs and message normalization |
| `azure_anomaly/` | Anomaly detection peer APIs, state handling, Azure Container Apps container build files |
| `gcp_risk/` | Risk analytics peer APIs and risk metric computation |
| `dashboard/` | Streamlit dashboard |
| `shared/` | Shared schemas, runtime, config, storage helpers, utility functions |
| `scripts/` | Local launcher, demos, smoke tests, cloud deployment orchestration |
| `infra/vm/` | VM bootstrap scripts and deployment notes |
| `docs/diagrams/` | Editable draw.io architecture diagrams |
| `dist/live/` | Persisted live deployment manifests and status |

## 6. Implemented Application Components

### 6.1 Shared Schemas and Runtime Foundation

The shared layer provides the core contracts used by every service.

Implemented components:

- typed Pydantic schemas for peers, heartbeats, market messages, normalized events, alerts, reviews, portfolios, risk snapshots, and ledger blocks
- common environment-based service settings loader
- runtime registration and heartbeat client
- capability discovery helper
- ledger append helper
- file-backed and Azure Blob-backed JSON state stores

Important implementation details:

- `shared/schemas/models.py` contains all inter-service data models
- `shared/config/settings.py` provides consistent environment-driven configuration across local and cloud execution
- `shared/runtime/service_runtime.py` performs peer registration, heartbeat refresh, capability lookup, and cross-service HTTP calls
- `shared/storage/state_store.py` provides the durable storage abstraction used by the Azure anomaly service

Compatibility fix already implemented:

- `StrEnum` now has a Python 3.10 fallback so Ubuntu 22.04 VM hosts can run the same codebase without requiring Python 3.11

### 6.2 Registry Service

The registry service is implemented as a FastAPI application and acts as the bootstrap and audit control plane for the QuantIAN overlay.

Delivered behavior:

- peer registration through `POST /registry/peers`
- heartbeat updates through `POST /registry/peers/{node_id}/heartbeat`
- peer listing and lookup
- capability-based peer discovery
- append-only ledger block creation and retrieval
- hash-chain verification through `GET /ledger/verify`

Persistence model:

- peers persist to `peers.json`
- ledger blocks persist to `ledger.json`
- peer state is refreshed dynamically based on last heartbeat timestamps

Peer freshness policy implemented in code:

- `online` when heartbeat age is within 90 seconds
- `stale` after 90 seconds
- `offline` after 180 seconds

The ledger is intentionally lightweight but technically defensible:

- each block stores the previous block hash
- payload content is hashed
- verification recomputes expected chain integrity

### 6.3 AWS Ingestion Peer

The ingestion service normalizes raw market sensor messages and drives downstream routing.

Delivered behavior:

- accepts sensor messages through `POST /ingestion/messages`
- computes short-window derived features:
  - `price_change_1m`
  - `volume_change_1m`
  - `notional_value`
- creates normalized `MarketEvent` payloads
- stores raw messages and normalized events
- routes events to peers discovered through registry capabilities
- appends ledger records for ingestion and routing actions

Routing behavior implemented:

- peers with `detect_anomalies` receive `/anomaly/analyze`
- peers with `store_market_events` receive `/risk/events`
- peers with `compute_risk` receive `/risk/compute`

Live evidence on April 21, 2026:

- `raw_messages = 16`
- `normalized_events = 16`
- `forwarded_events = 16`
- `routing_failures = 0`

### 6.4 Azure Anomaly Peer

The anomaly service is the most infrastructure-sensitive component and is now deployed in its final working form on Azure Container Apps.

Delivered behavior:

- accepts normalized events through `POST /anomaly/analyze`
- stores alert history and rolling symbol history
- exposes current alerts through `GET /anomaly/alerts`
- exposes individual alert lookup through `GET /anomaly/alerts/{alert_id}`
- accepts human review through `POST /anomaly/alerts/{alert_id}/review`
- appends ledger events for alert creation and review

Detection logic implemented:

- rule-based anomaly scoring from price and volume deltas
- Isolation Forest scoring when enough history exists
- alert threshold default of `0.82`
- rolling history window of `60` feature observations per symbol
- severity mapping of `low`, `medium`, `high`, `critical`

Reason strings include interpretable context such as:

- `price spike`
- `volume surge`
- `isolation forest outlier`
- score breakdown fragments like `rule=...` and `model=...`

Persistence model:

- local development can use file-backed JSON state
- cloud deployment uses `AzureBlobJsonStateStore`
- state includes both alert objects and historical feature windows

This storage change was essential for the Azure hosting pivot. Without it, App Service or Container Apps restarts would have caused alert and history loss.

Live evidence on April 21, 2026:

- `alerts = 5`
- `tracked_symbols = 4`
- `sklearn_enabled = true`
- `storage_backend = AzureBlobJsonStateStore`

Current live alerts include:

- one confirmed BTCUSD alert
- pending-review alerts for AAPL, BTCUSD, ETHUSD, and MSFT

### 6.5 GCP Risk Peer

The risk service stores market events, stores the demo portfolio, and produces risk snapshots.

Delivered behavior:

- accepts market events through `POST /risk/events`
- stores a portfolio through `POST /risk/portfolio`
- returns the current portfolio through `GET /risk/portfolio`
- computes a new snapshot through `POST /risk/compute`
- returns the latest snapshot through `GET /risk/latest`
- returns history through `GET /risk/history`

Risk metrics implemented:

- annualized volatility from portfolio return series
- historical Value at Risk at 95%
- maximum drawdown
- rolling 1-day return

The service runs with `auto_compute=True`, so risk can be recomputed as events arrive when a portfolio is already loaded.

Live evidence on April 21, 2026:

- `symbols_tracked = 4`
- `portfolio_loaded = true`
- `snapshots = 33`

Current live portfolio:

```json
{
  "portfolio_id": "demo_portfolio",
  "positions": [
    {"symbol": "BTCUSD", "weight": 0.4},
    {"symbol": "ETHUSD", "weight": 0.3},
    {"symbol": "AAPL", "weight": 0.2},
    {"symbol": "MSFT", "weight": 0.1}
  ]
}
```

Current live risk snapshot:

```json
{
  "snapshot_id": "risk_ec533c167acb",
  "portfolio_id": "demo_portfolio",
  "as_of": "2026-04-21T05:53:28.189437+00:00",
  "volatility": 0.382435,
  "value_at_risk_95": -0.030545,
  "max_drawdown": -0.030545,
  "rolling_return_1d": -0.005706
}
```

### 6.6 Dashboard

The Streamlit dashboard is implemented as an operational demo surface for the full stack.

Delivered tabs and functions:

- `Overview`: health cards for registry, ingestion, anomaly, and risk
- `Controls`: seed portfolio, send market cycle, send anomalous cycle, recompute risk
- `Peers`: live peer list from the registry
- `Alerts`: live alert table and review submission UI
- `Risk`: portfolio display, latest snapshot, and history table
- `Ledger`: ledger verification and block listing

The dashboard is not a mockup. It interacts with the live services through their public endpoints and is part of the current working deployment.

### 6.7 Simulator and Demo Tooling

The repository now includes multiple execution paths for development and demonstration:

- `scripts/run_local_stack.py`: launches the full local stack, optionally seeds the portfolio and starts autoplay
- `scripts/publish_simulation.py`: publishes additional market traffic into a running stack
- `scripts/local_flow_demo.py`: dependency-light local demo
- `scripts/discovery_flow_demo.py`: discovery-driven local demo
- `simulator/mqtt_publisher/`: market sensor simulator and MQTT-compatible publisher utilities

### 6.8 Draw.io Architecture Deliverables

The draw.io implementation is also complete enough to support reporting and presentation.

Delivered editable diagrams:

- `docs/diagrams/quantian_local_mvp.drawio`
- `docs/diagrams/quantian_final_cloud.drawio`

The final cloud diagram has already been updated to reflect the actual live topology:

- AWS VM
- Azure Container Apps
- Azure Blob Storage
- GCP VM

This matters because the final deployment no longer matches the earlier all-VM assumption.

## 7. Deployment Automation

### 7.1 Primary Orchestration Entry Point

The main deployment automation now lives in:

- `scripts/cloud_deploy.py`

Implemented commands:

- `package`
- `package-azure`
- `provision-aws`
- `provision-azure`
- `provision-gcp`
- `deploy-azure`
- `bootstrap`
- `status`
- `go-live`

The deployment path is designed to be reusable and mostly idempotent through persisted manifests in `dist/live/`.

### 7.2 AWS and GCP VM Bootstrap

The VM bootstrap process is implemented in:

- `infra/vm/bootstrap_quantian_host.sh`

Implemented bootstrap behavior:

- installs Python, venv, pip, and curl
- creates `/opt/quantian`
- creates `/var/lib/quantian`
- creates a Python virtual environment on the host
- installs dependencies from `requirements.txt`
- writes `/etc/quantian/common.env`
- creates and enables `systemd` services
- waits for local health endpoints before exiting

Systemd units created:

- AWS host:
  - `quantian-registry.service`
  - `quantian-ingestion.service`
  - `quantian-dashboard.service`
- GCP host:
  - `quantian-risk.service`

Expected public ports:

- AWS: `8000`, `8001`, `8501`
- GCP: `8003`

### 7.3 Deployment Bundle Packaging

The deployment bundle is built through:

- `scripts/package_deployment_bundle.sh`

The tarball intentionally excludes:

- `.venv`
- `data`
- `dist`
- `build`
- `__pycache__`
- compiled Python artifacts
- `.docx`
- `.pkg`
- macOS metadata files
- local tool caches

This cleanup matters because the bundle is intended for repeatable remote host bootstrap, not for copying local development artifacts into production hosts.

### 7.4 Azure Container Apps Deployment Path

The Azure deployment is now a complete source-to-container path.

Implemented behavior in `scripts/cloud_deploy.py`:

- create or reuse Azure resource group
- explicitly ensure required providers are registered
- create or reuse Container Apps environment
- create or reuse Azure Container Registry
- create or reuse Azure Storage Account
- create or reuse Blob container
- build a filtered Azure deployment context under `dist/azure-containerapp-src`
- remote-build the image in ACR
- create or update the Container App
- inject runtime environment variables
- inject Blob storage connection string as a secret
- save resulting metadata to `dist/live/azure.json`

Runtime environment variables set for the Container App include:

- service host and port
- runtime enablement flags
- heartbeat and timeout settings
- registry and peer URLs
- storage backend selection
- Blob storage secret reference and container details
- service base URL

### 7.5 Manifest-Driven Operating Model

The live deployment now persists machine-readable deployment state under:

- `dist/live/aws.json`
- `dist/live/azure.json`
- `dist/live/gcp.json`
- `dist/live/status.json`

This allows:

- reusing existing infrastructure without reprovisioning everything
- bootstrapping only missing pieces
- checking current public health independently of provisioning
- documenting the exact live environment from repo state

## 8. Major Pivots, Blockers, and Fixes

### 8.1 Original Azure VM Path Failed

The original plan placed the Azure anomaly service on a VM. That approach was blocked on April 21, 2026 by Azure subscription capacity and quota constraints in `eastus`.

Observed blockers:

- `Standard_B1s` capacity/unavailability
- `standardBpsv2Family` quota at `0`
- `standardDPSv5Family` quota at `0`

This blocked the original three-VM design from reaching go-live.

### 8.2 App Service Pivot Also Failed

The first pivot moved Azure anomaly from VM to Azure App Service. Functionally that would have been acceptable, but the subscription was also blocked there.

Observed blockers:

- Basic VMs quota at `0`
- Free VMs quota at `0`

That made App Service non-viable in the current Azure subscription.

### 8.3 Final Azure Pivot to Container Apps

The second pivot moved Azure anomaly to Azure Container Apps and moved anomaly persistence to Azure Blob Storage.

This was the successful final design because:

- it avoided the Azure VM quota blocker
- it avoided the App Service plan quota blocker
- it preserved the same `/anomaly/*` API contract
- it gave the anomaly service durable storage

### 8.4 Additional Azure Fixes Required

Container Apps provisioning still required several technical fixes:

- explicit provider registration for `Microsoft.App`, `Microsoft.ContainerRegistry`, and `Microsoft.Storage`
- handling an Azure CLI internal error during implicit provider registration
- passing the generated Dockerfile path explicitly to `az acr build` after an initial `Unable to find 'Dockerfile'` failure

### 8.5 Ubuntu 22.04 Python Compatibility Fixes

The AWS and GCP VM bootstrap path initially failed because Ubuntu 22.04 hosts default to Python 3.10 while the repo had drifted into Python 3.11+ assumptions.

Implemented fixes:

- lowered `numpy` and `pandas` constraints in `requirements.txt` to versions compatible with Python 3.10
- added a `StrEnum` fallback for Python versions earlier than 3.11

Without these fixes, the VM hosts could not run the current codebase after package installation.

### 8.6 Health Probe Reliability Fix

The Azure anomaly service was healthy in practice, but `scripts/cloud_deploy.py status` initially reported false negatives because the original probe logic used Python HTTP handling that did not behave reliably against the Container Apps HTTPS endpoint.

Implemented fix:

- changed the deployment health probe to use `curl -fsSL --max-time 5`

This made status reporting consistent with the actual public service behavior.

### 8.7 SSH and Manifest Reuse Fixes

Additional deployment robustness fixes were also implemented:

- AWS/GCP manifest reuse logic now works better with mixed existing and newly provisioned infrastructure
- missing `ssh_user` values default safely to `ubuntu` where needed for remote bundle upload and bootstrap

## 9. Verification and Testing

### 9.1 Local Verification

The repository includes:

- `scripts/service_smoke_test.py`

This smoke test runs all four core services in-process with FastAPI test clients and verifies:

- registry registration and heartbeat
- ingestion message normalization
- anomaly detection and alert storage
- portfolio configuration
- risk computation
- ledger verification

This smoke test passed after the storage and compatibility changes.

### 9.2 Deployment Verification

The live deployment has been validated through:

- `.venv/bin/python scripts/cloud_deploy.py status`
- direct `curl` checks of all public health endpoints
- live registry peer listing
- live ledger verification
- live anomaly alert listing
- live risk portfolio query
- live risk snapshot query

### 9.3 Current Operational Evidence

Operational evidence captured on April 21, 2026 includes:

- three online peers registered in the overlay
- valid ledger chain with `355` blocks at verification time
- five persisted anomaly alerts
- four tracked market symbols
- demo portfolio loaded into the risk peer
- `33` risk snapshots stored
- non-zero live risk metrics now present in the latest snapshot

## 10. Documentation and Reporting Deliverables Completed

The following documentation and diagram deliverables now exist in the repository:

- `README.md`
- `docs/MASTER_TECHNICAL_DOCUMENT.md`
- `infra/vm/DEPLOYMENT_NOTES.md`
- `docs/diagrams/README.md`
- `docs/diagrams/quantian_local_mvp.drawio`
- `docs/diagrams/quantian_final_cloud.drawio`
- `docs/LIVE_IMPLEMENTATION_TECHNICAL_DOCUMENT.md`

This means the project is now documented at three levels:

- design intent and scope
- deployment procedure
- current implementation and live status

## 11. What Has Been Achieved

In practical engineering terms, the project has already achieved the following:

- a working cross-cloud service split across AWS, Azure, and GCP
- a functioning registry/discovery/heartbeat control plane
- a functioning append-only blockchain-style ledger
- a working ingestion-to-anomaly-to-risk event flow
- a working dashboard that can interact with the live services
- anomaly state persistence that survives Azure service restarts
- automated provisioning and deployment scripts
- repeatable VM bootstrap
- repeatable Azure container deployment
- live manifests that record the actual deployed environment
- local smoke testing and local full-stack execution paths
- draw.io architecture diagrams aligned with the final live topology

## 12. Known Limitations and Next Hardening Steps

The current system is live and demonstrable, but it is still an MVP and not a hardened production platform.

Current limitations:

- the registry is a central bootstrap point rather than a fully decentralized overlay
- VM-hosted AWS and GCP services are exposed by public IP rather than behind managed ingress or custom domains
- observability is basic; there is no centralized metrics, tracing, or structured log pipeline
- secrets and cloud credentials still depend on local CLI-authenticated deployment workflows
- Azure Container Apps runs with a single replica for determinism rather than scale-out
- the risk model is intentionally lightweight and uses local event history rather than institutional-grade market data pipelines
- anomaly detection is based on a compact rules-plus-Isolation-Forest approach rather than a continuously trained ML platform

Reasonable next steps:

- add HTTPS fronting and domain management for AWS and GCP services
- add centralized logging and health dashboards
- add CI automation for smoke tests and packaging validation
- add more robust risk metrics and alert analytics
- add managed secret storage and tighter IAM scoping
- expand the draw.io deliverables into presentation exports for reporting

## 13. Final Technical Position

As of April 21, 2026, QuantIAN is no longer just a design proposal. It is an implemented, documented, and publicly reachable multi-cloud system with live runtime evidence.

The most important engineering outcome is that the project reached a workable final architecture despite Azure quota constraints. The final hybrid design preserves the original business flow, satisfies the project pillars, and is supported by deployment automation, persistence, test coverage, and architecture documentation.
