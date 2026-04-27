#!/usr/bin/env bash
# QuantIAN one-shot bootstrap: python venv + deps, node deps, mosquitto,
# quick smoke check. Idempotent — safe to re-run.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

GREEN='\033[1;32m'; YELLOW='\033[1;33m'; RED='\033[1;31m'; NC='\033[0m'
step()  { echo -e "${GREEN}==>${NC} $*"; }
warn()  { echo -e "${YELLOW}!!${NC} $*"; }
die()   { echo -e "${RED}xx${NC} $*" >&2; exit 1; }
have()  { command -v "$1" >/dev/null 2>&1; }

# ------- Pre-flight ---------------------------------------------------
have python3 || die "python3 not found. Install Python 3.11+."
have node    || die "node not found. Install Node 20+."
have npm     || die "npm not found."
PYVER="$(python3 -c 'import sys;print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
case "$PYVER" in
  3.11|3.12|3.13|3.14) ;;
  *) warn "Python $PYVER detected — project is tested on 3.11–3.13." ;;
esac

# ------- Python venv + deps ------------------------------------------
if [ ! -d .venv ]; then
  step "creating .venv"
  python3 -m venv .venv
else
  step ".venv already present"
fi

step "installing python deps"
./.venv/bin/pip install --upgrade pip >/dev/null
./.venv/bin/pip install -r requirements.txt

# ------- Node deps ---------------------------------------------------
step "installing web dashboard deps"
(cd web_dashboard && npm install --silent --no-audit --no-fund)

# ------- Mosquitto (optional but recommended) -------------------------
if ! have mosquitto; then
  warn "mosquitto not found. For the IoT pipeline, install:"
  warn "  macOS:   brew install mosquitto"
  warn "  Ubuntu:  sudo apt install mosquitto mosquitto-clients"
  warn "  Docker:  docker run -d --name mosquitto -p 1883:1883 eclipse-mosquitto"
else
  step "mosquitto binary detected at $(command -v mosquitto)"
fi

# ------- .env ---------------------------------------------------------
if [ ! -f .env ] && [ -f .env.example ]; then
  cp .env.example .env
  step "copied .env.example -> .env (edit as needed)"
fi

# ------- Smoke check on apps importing --------------------------------
step "smoke-importing every FastAPI app"
./.venv/bin/python - <<'PY'
from registry_service.main import app as a
from aws_ingestion.main import app as b
from azure_anomaly.main import app as c
from gcp_risk.main import app as d
from iot.main import app as e
print("  ok:", ", ".join(x.title for x in (a, b, c, d, e)))
PY

# ------- Pytest (quick) -----------------------------------------------
step "running pytest (quick)"
./.venv/bin/pytest -q --color=yes || die "tests failed"

echo
echo -e "${GREEN}Setup complete.${NC}"
echo
echo "Next:"
echo "  1. start the broker:        mosquitto -d -p 1883"
echo "  2. start all services:      make stack"
echo "  3. in a new terminal:       make dashboard   # React on :5174"
echo "  4. push market data:        make push-ticks"
echo "  5. open the dashboard:      http://localhost:5174"
