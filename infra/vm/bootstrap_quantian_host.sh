#!/usr/bin/env bash
set -euo pipefail

ROLE="${1:?usage: bootstrap_quantian_host.sh <aws|azure|gcp>}"
REPO_DIR="${REPO_DIR:-/opt/quantian}"
DATA_ROOT="${DATA_ROOT:-/var/lib/quantian}"
DEPLOY_USER="${DEPLOY_USER:-$(id -un)}"

REGISTRY_URL="${REGISTRY_URL:?REGISTRY_URL is required}"
INGESTION_URL="${INGESTION_URL:?INGESTION_URL is required}"
ANOMALY_URL="${ANOMALY_URL:?ANOMALY_URL is required}"
RISK_URL="${RISK_URL:?RISK_URL is required}"

sudo apt-get update
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y python3 python3-venv python3-pip curl

sudo mkdir -p "$REPO_DIR" "$DATA_ROOT" /etc/quantian
sudo chown -R "$DEPLOY_USER":"$DEPLOY_USER" "$REPO_DIR" "$DATA_ROOT"

cd "$REPO_DIR"

python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt

sudo tee /etc/quantian/common.env >/dev/null <<EOF
APP_ENV=cloud
SERVICE_HOST=0.0.0.0
PYTHONPATH=$REPO_DIR
QUANTIAN_DATA_DIR=$DATA_ROOT
ENABLE_SERVICE_RUNTIME=true
REQUEST_TIMEOUT_SECONDS=8
HEARTBEAT_INTERVAL_SECONDS=20
REGISTRY_URL=$REGISTRY_URL
LEDGER_URL=$REGISTRY_URL
AWS_INGESTION_URL=$INGESTION_URL
AZURE_ANOMALY_URL=$ANOMALY_URL
GCP_RISK_URL=$RISK_URL
BROWSER_GATHER_USAGE_STATS=false
EOF

create_unit() {
  local unit_name="$1"
  local env_file="$2"
  local exec_start="$3"

  sudo tee "/etc/systemd/system/${unit_name}.service" >/dev/null <<EOF
[Unit]
Description=${unit_name}
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$DEPLOY_USER
WorkingDirectory=$REPO_DIR
EnvironmentFile=/etc/quantian/common.env
EnvironmentFile=-$env_file
ExecStart=$exec_start
Restart=always
RestartSec=5
KillSignal=SIGINT
TimeoutStopSec=30

[Install]
WantedBy=multi-user.target
EOF
}

write_service_env() {
  local env_file="$1"
  local body="$2"
  printf "%s\n" "$body" | sudo tee "$env_file" >/dev/null
}

enable_services() {
  sudo systemctl daemon-reload
  sudo systemctl enable "$@"
  sudo systemctl restart "$@"
}

wait_for_http() {
  local url="$1"
  local timeout_seconds="${2:-90}"
  local deadline=$((SECONDS + timeout_seconds))
  until curl -fsS "$url" >/dev/null 2>&1; do
    if (( SECONDS >= deadline )); then
      echo "Timed out waiting for $url" >&2
      return 1
    fi
    sleep 2
  done
}

case "$ROLE" in
  aws)
    write_service_env /etc/quantian/quantian-registry.env ""
    write_service_env /etc/quantian/quantian-ingestion.env "AWS_INGESTION_BASE_URL=$INGESTION_URL"
    write_service_env /etc/quantian/quantian-dashboard.env ""

    create_unit \
      quantian-registry \
      /etc/quantian/quantian-registry.env \
      "$REPO_DIR/.venv/bin/python -m uvicorn registry_service.main:app --host 0.0.0.0 --port 8000"

    create_unit \
      quantian-ingestion \
      /etc/quantian/quantian-ingestion.env \
      "$REPO_DIR/.venv/bin/python -m uvicorn aws_ingestion.main:app --host 0.0.0.0 --port 8001"

    create_unit \
      quantian-dashboard \
      /etc/quantian/quantian-dashboard.env \
      "$REPO_DIR/.venv/bin/streamlit run dashboard/app.py --server.headless true --server.address 0.0.0.0 --server.port 8501"

    enable_services quantian-registry.service quantian-ingestion.service quantian-dashboard.service
    wait_for_http "http://127.0.0.1:8000/health"
    wait_for_http "http://127.0.0.1:8001/health"
    wait_for_http "http://127.0.0.1:8501"
    ;;
  azure)
    write_service_env /etc/quantian/quantian-anomaly.env "AZURE_ANOMALY_BASE_URL=$ANOMALY_URL"

    create_unit \
      quantian-anomaly \
      /etc/quantian/quantian-anomaly.env \
      "$REPO_DIR/.venv/bin/python -m uvicorn azure_anomaly.main:app --host 0.0.0.0 --port 8002"

    enable_services quantian-anomaly.service
    wait_for_http "http://127.0.0.1:8002/health"
    ;;
  gcp)
    write_service_env /etc/quantian/quantian-risk.env "GCP_RISK_BASE_URL=$RISK_URL"

    create_unit \
      quantian-risk \
      /etc/quantian/quantian-risk.env \
      "$REPO_DIR/.venv/bin/python -m uvicorn gcp_risk.main:app --host 0.0.0.0 --port 8003"

    enable_services quantian-risk.service
    wait_for_http "http://127.0.0.1:8003/health"
    ;;
  *)
    echo "Unknown role: $ROLE" >&2
    exit 1
    ;;
esac

echo "Bootstrap completed for role: $ROLE"
