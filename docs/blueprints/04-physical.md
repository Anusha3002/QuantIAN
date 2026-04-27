# Blueprint 04 — Physical / Deployment View

| Legend Box                  | Value                                                      |
|-----------------------------|------------------------------------------------------------|
| **Architecture Domain**     | Technical                                                  |
| **Blueprint Type**          | Deployment Diagram                                         |
| **Scope**                   | Project                                                    |
| **Level of Abstraction**    | Physical                                                   |
| **State**                   | As-Is (live) + To-Be (planned hardening)                   |
| **Communication Objective** | Concrete cloud resources that back each logical service    |
| **Authors**                 | QuantIAN Team                                              |
| **Revision Date**           | 2026-04-21                                                 |
| **Status**                  | Working Draft                                              |

## Deployment diagram

```mermaid
flowchart TB
  subgraph USER["👤 Operator"]
    BROWSER[["Browser<br/>streamlit + react"]]
  end

  subgraph AWS_CLOUD["☁️ AWS"]
    direction TB
    subgraph EC2["EC2 · Ubuntu 22.04"]
      REG_SVC["Registry + Ledger<br/>uvicorn :8000"]
      ING_SVC["Ingestion Peer<br/>uvicorn :8001"]
      STREAM["Streamlit Dashboard<br/>:8501"]
      IOT_SVC["IoT Bridge<br/>uvicorn :8004"]
    end
    EIP[["Elastic IP<br/>3.217.147.34"]]
    SG[["Security Group<br/>sg-...<br/>allow 22 + app ports"]]
    subgraph IOT_CORE["(planned) AWS IoT Core"]
      MQTT_BROKER[["MQTT Broker<br/>TLS on 8883"]]
    end
    EIP --- EC2
    SG --- EC2
    IOT_CORE -.subscribe topic:<br/>quantian/market/+/+.-> IOT_SVC
  end

  subgraph AZURE_CLOUD["☁️ Azure"]
    direction TB
    ACR[("Azure Container Registry<br/>qtanacr....azurecr.io")]
    subgraph ACA["Azure Container Apps (env: quantian-azure-env)"]
      ANOM_SVC["Anomaly Peer<br/>container :8002"]
    end
    BLOB[("Blob Storage<br/>container: quantian-state")]
    ACR -- image --> ACA
    ACA -- JsonStateStore --> BLOB
  end

  subgraph GCP_CLOUD["☁️ GCP"]
    direction TB
    subgraph GCE["Compute Engine · e2-small"]
      RISK_SVC["Risk Peer<br/>uvicorn :8003"]
    end
    FW[["Firewall Rule<br/>allow :8003 / :22"]]
    FW --- GCE
  end

  subgraph LOCAL["💻 Local dev (optional)"]
    DOCKER[["docker-compose.yml<br/>mosquitto + 5 peers"]]
  end

  BROWSER -- HTTPS --> ACA
  BROWSER -- HTTP --> EC2
  BROWSER -- HTTP --> GCE

  IOT_SVC -- POST /ingestion/messages --> ING_SVC
  ING_SVC -- POST /anomaly/analyze --> ANOM_SVC
  ING_SVC -- POST /risk/events --> RISK_SVC

  ANOM_SVC -.register + heartbeat.-> REG_SVC
  RISK_SVC -.register + heartbeat.-> REG_SVC
  IOT_SVC  -.register + heartbeat.-> REG_SVC
  ING_SVC  -.register + heartbeat.-> REG_SVC

  ANOM_SVC -.append ledger block.-> REG_SVC
  RISK_SVC -.append ledger block.-> REG_SVC
  ING_SVC  -.append ledger block.-> REG_SVC

  classDef aws fill:#F59E0B22,stroke:#F59E0B,color:#F59E0B;
  classDef azr fill:#38BDF822,stroke:#38BDF8,color:#38BDF8;
  classDef gcp fill:#10B98122,stroke:#10B981,color:#10B981;
  classDef local fill:#A78BFA22,stroke:#A78BFA,color:#A78BFA;
  class AWS_CLOUD aws
  class AZURE_CLOUD azr
  class GCP_CLOUD gcp
  class LOCAL local
```

## Cloud resource inventory (live)

Pinned from [../LIVE_IMPLEMENTATION_TECHNICAL_DOCUMENT.md](../LIVE_IMPLEMENTATION_TECHNICAL_DOCUMENT.md):

### AWS
| Resource     | Value |
|--------------|-------|
| Region       | us-east-1 |
| Instance     | `i-053e7ea72e9c00e01` (Ubuntu 22.04, t3.small) |
| Elastic IP   | `3.217.147.34` |
| Security grp | `sg-0ebf64ab6b66bd8d5` |
| Services     | Registry, Ingestion, IoT Bridge, Streamlit |

### Azure
| Resource         | Value |
|------------------|-------|
| Resource group   | `quantian-rg` |
| Environment      | `quantian-azure-env` (Container Apps) |
| App              | `quantian-azure-anomaly` |
| Image            | `qtanacr...azurecr.io/quantian/azure-anomaly:20260421053208` |
| Blob storage     | `qtanom...` / container `quantian-state` |
| Endpoint         | `https://quantian-azure-anomaly.yellowocean-36a09ba3.eastus.azurecontainerapps.io` |

### GCP
| Resource | Value |
|----------|-------|
| Project  | `nyu-clopud-hw2` |
| Zone     | `us-central1-a` |
| Instance | `quantian-gcp-risk` (Compute Engine) |
| Public IP | `35.192.123.119` |

## Deployment pipeline

```mermaid
flowchart LR
  DEV["make test<br/>green"]
  GH[["GitHub push → CI<br/>pytest + tsc --noEmit + build"]]
  DEPLOY["scripts/cloud_deploy.py go-live"]
  AWS["AWS provisioning<br/>(EC2 + EIP + SG)"]
  AZURE["Azure provisioning<br/>(ACR + Container Apps + Blob)"]
  GCP["GCP provisioning<br/>(Compute Engine + firewall)"]
  BOOT["infra/vm/bootstrap_quantian_host.sh<br/>runs on every VM"]

  DEV --> GH --> DEPLOY
  DEPLOY --> AWS --> BOOT
  DEPLOY --> AZURE
  DEPLOY --> GCP --> BOOT
```

## What's local vs. cloud right now

| Concern              | Local dev                                | Production cloud |
|----------------------|------------------------------------------|------------------|
| Process orchestration | `run_local_stack.py` or `docker compose` | `systemd` (AWS / GCP), Container Apps revision controller (Azure) |
| MQTT broker          | Mosquitto on :1883                       | AWS IoT Core (TLS on :8883) |
| Registry + ledger persistence | `data/runtime/registry_service/*.json` | JSON file on EC2 (can upgrade to DynamoDB) |
| Anomaly persistence  | JSON file                                | Azure Blob Storage (`AzureBlobJsonStateStore`) |
| Risk persistence     | JSON file                                | JSON file on GCE (can upgrade to BigQuery) |
| TLS                  | none                                     | Azure Container Apps terminates TLS; AWS/GCP still plain HTTP (to-do) |
