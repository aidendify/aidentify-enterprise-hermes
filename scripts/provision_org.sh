#!/usr/bin/env bash
# Provision a new tenant org (client company) on an Enterprise-Hermes host.
# Usage: ./scripts/provision_org.sh <slug> <"Display Name">
set -e
cd "$(dirname "$0")/.."
SLUG="${1:?usage: provision_org.sh <slug> <name>}"
NAME="${2:-$SLUG}"
DATA_DIR="_data/$SLUG"

mkdir -p "$DATA_DIR/workspace"
python3 - "$SLUG" "$NAME" <<'PY'
import json, sys, os
slug, name = sys.argv[1], sys.argv[2]
orgs_file = "_data/orgs.json"
orgs = json.load(open(orgs_file)) if os.path.exists(orgs_file) else {}
orgs.setdefault(slug, {"name": name, "enabled": True,
                        "demo_tokens": ["operator-demo-token", "manager-demo-token"],
                        "created_at": "newly-provisioned"})
json.dump(orgs, open(orgs_file, "w"), indent=2)
print("provisioned org:", slug)
PY
echo "→ org '$SLUG' enabled. Audit log lives at $DATA_DIR/audit.log"