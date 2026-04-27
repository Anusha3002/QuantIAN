#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

check() {
  local name="$1"
  local url="$2"

  if curl -fsS "$url" >/dev/null 2>&1; then
    echo "[ok] $name -> $url"
  else
    echo "[down] $name -> $url"
  fi
}

check "Registry" "http://127.0.0.1:8000/health"
check "Ingestion" "http://127.0.0.1:8001/health"
check "Anomaly" "http://127.0.0.1:8002/health"
check "Risk" "http://127.0.0.1:8003/health"
check "Dashboard" "http://127.0.0.1:8501"
