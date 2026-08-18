#!/usr/bin/env bash
set -e
cd /opt/data/aidentify/products/enterprise-hermes
/opt/data/aidentify/products/enterprise-hermes/.venv/bin/python -m pytest tests -q 2>&1 | tail -30