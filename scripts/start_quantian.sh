#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [[ ! -x ".venv/bin/python" ]]; then
  python3 -m venv .venv
fi

if [[ ! -x ".venv/bin/uvicorn" ]]; then
  .venv/bin/pip install -r requirements.txt
fi

exec .venv/bin/python scripts/run_local_stack.py --with-dashboard --autoplay --cycles 12 --interval 1 --reset-state
