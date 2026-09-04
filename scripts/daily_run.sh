#!/usr/bin/env bash
# Daily Hermes run: scan, tailor, queue for review.
# Install: crontab -e -> "0 9,17 * * * /path/to/ApplyJin/scripts/daily_run.sh"
set -euo pipefail
cd "$(dirname "$0")/.."

VENV_PY=".venv/bin/python"
[ -x "$VENV_PY" ] || { echo "venv missing — run: python -m venv .venv && pip install -e ."; exit 1; }

"$VENV_PY" -m hermes.cli run --offline=false 2>&1 | tee -a data/hermes_daily.log
