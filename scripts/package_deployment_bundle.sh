#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUTPUT_PATH="${1:-$ROOT_DIR/dist/quantian-deploy.tar.gz}"

mkdir -p "$(dirname "$OUTPUT_PATH")"

export COPYFILE_DISABLE=1

tar \
  --exclude=".DS_Store" \
  --exclude="._*" \
  --exclude=".venv" \
  --exclude="data" \
  --exclude="dist" \
  --exclude="build" \
  --exclude="__pycache__" \
  --exclude="*.pyc" \
  --exclude="*.pyo" \
  --exclude="*.pyd" \
  --exclude="*.docx" \
  --exclude="*.pkg" \
  --exclude=".pytest_cache" \
  --exclude=".mypy_cache" \
  --exclude=".ruff_cache" \
  -czf "$OUTPUT_PATH" \
  -C "$ROOT_DIR" \
  .

echo "$OUTPUT_PATH"
