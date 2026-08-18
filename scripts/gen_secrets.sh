#!/usr/bin/env bash
# Generate a strong random AUDIT_HMAC_KEY and API token.
set -euo pipefail
echo "AUDIT_HMAC_KEY=$(openssl rand -hex 32)"
echo "ADMIN_API_TOKEN=$(openssl rand -hex 16)"
echo "Copy these into your .env / secrets vault. Never commit."
