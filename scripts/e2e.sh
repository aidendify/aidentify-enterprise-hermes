#!/usr/bin/env bash
# Enterprise-Hermes end-to-end smoke: gate approval flow + real-model agent.
set -u
B="localhost:8080"
sleep 3
echo "=== 0) health ==="
curl -s -m 10 $B/health
echo; echo "=== 1) HIGH-risk -> expect 409, capture request_id ==="
R=$(curl -s -X POST $B/tools/run -H "Authorization: Bearer operator-demo-token" \
  -H 'content-type: application/json' \
  -d '{"org":"acme","tool":"code.run_tests","args":{"cmd":"pytest","cwd":"/opt/data/aidentify/products/enterprise-hermes"}}')
echo "$R"
REQ=$(printf '%s' "$R" | sed -n 's/.*"request_id":"\([^"]*\)".*/\1/p')
echo "request_id=$REQ"
echo "=== 2) approve the gate ==="
curl -s -X POST "$B/gate/$REQ/decide?org=acme" -H "Authorization: Bearer manager-demo-token" \
  -H 'content-type: application/json' -d '{"approver":"manager","approve":true,"reason":"CI approval"}'
echo; echo "=== 3) execute high-risk with approved req_id ==="
curl -s -X POST $B/tools/run -H "Authorization: Bearer operator-demo-token" \
  -H 'content-type: application/json' \
  -d "{\"org\":\"acme\",\"tool\":\"code.run_tests\",\"args\":{\"cmd\":\"pytest\",\"cwd\":\"/opt/data/aidentify/products/enterprise-hermes\"},\"request_id\":\"$REQ\"}"
echo; echo "=== 4) general agent run (REAL model via OpenRouter) ==="
timeout 180 curl -s -m 170 -X POST $B/agents/run -H "Authorization: Bearer operator-demo-token" \
  -H 'content-type: application/json' \
  -d '{"org":"acme","prompt":"Plan a small billing API service. Use the notes.save tool to write billing-notes.md containing three bullet points on the design, then call general.status, then reply with a 2-line summary."}'
echo; echo "=== 5) audit trail (last 8 entries) ==="
curl -s "$B/audit?org=acme" -H "Authorization: Bearer manager-demo-token" \
  | sed -n 's/.*"records":\[/&/p' | head -c 600
echo