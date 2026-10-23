#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")/.."
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.lock.txt
npm ci --no-audit --no-fund
npm run build
printf 'Run: .venv/bin/python scripts/start.py --open\n'
