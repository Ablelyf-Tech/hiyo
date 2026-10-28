#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.lock
.venv/bin/python -m pip install --no-deps -e '.[test]'
(cd dashboard && npm ci --cache /workspace/.npm-cache --no-audit --no-fund && npm run build && npm test)
.venv/bin/python -m pytest -q
