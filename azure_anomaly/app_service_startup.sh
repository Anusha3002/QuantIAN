#!/usr/bin/env bash
set -euo pipefail

PORT_VALUE="${PORT:-${WEBSITES_PORT:-8000}}"

exec python -m uvicorn azure_anomaly.main:app --host 0.0.0.0 --port "$PORT_VALUE"
