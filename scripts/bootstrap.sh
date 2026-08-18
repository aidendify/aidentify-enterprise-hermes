#!/usr/bin/env bash
# Enterprise Agent Ops — bootstrap.
# Copies .env.example -> .env (no-op if present), runs checks.
set -euo pipefail
cd "$(dirname "$0")/.."

if [ ! -f .env ]; then
  cp .env.example .env
  echo "Created .env from .env.example — fill values before deploy."
else
  echo ".env already exists — leaving as-is."
fi

echo "Running pack validator..."
python3 scripts/validate_pack.py

echo "Bootstrap OK."
