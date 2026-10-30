#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ -d .venv ]]; then source .venv/bin/activate; fi
python -m py_compile backend/app.py
node --check frontend/app.js
python -m pytest -q
