#!/usr/bin/env bash
# Weekly learning cycle: email triage -> learn -> apply style guide.
# Install: crontab -e -> "0 8 * * MON /path/to/ApplyJin/scripts/learn_weekly.sh"
set -euo pipefail
cd "$(dirname "$0")/.."

VENV_PY=".venv/bin/python"
[ -x "$VENV_PY" ] || { echo "venv missing"; exit 1; }

# 1. Pull outcome emails into the tracker (skip silently if not configured).
"$VENV_PY" -m hermes.cli triage-email --apply 2>/dev/null || true

# 2. Learn + promote the style guide if data supports it.
"$VENV_PY" -m hermes.cli learn --apply 2>&1 | tee -a data/hermes_learn.log
