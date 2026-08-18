# Enterprise-Hermes

**The full autonomous Hermes agent — orchestration, skills, tool use, and all —
running entirely inside your network, with SSO/RBAC, immutable audit,
human-approval gates, and zero data egress, managed from one admin console.**

A governed, self-hosted appliance built on the MIT-licensed [Hermes Agent](https://github.com/NousResearch/hermes-agent)
engine (see `NOTICE` for attribution). This is the *general*-agent version of
`enterprise-agent-ops`: instead of five canned ops bots, you get a real agent
that can be pointed at **any** task — but every tool call is wrapped in
enterprise governance.

## What's inside

| Layer | What it does |
|---|---|
| **Hermes engine** (vendored, MIT) | general agent loop, provider-agnostic LLM, tools, skills, memory, orchestration |
| **Governance shell** | SSO/RBAC (OIDC/SAML plug point), immutable HMAC-chained audit, human-approval gates, least-privilege tool allowlist, **zero egress by default** |
| **Multi-org control plane** | per-org isolated profiles/workspaces/audit, admin web console, org provisioning |
| **Orchestration** | concurrent agent workstreams, multi-agent delegation |
| **Appliance** | `./enthermes up` — one-command Docker stack |

## Quickstart (no external model required for governance)

```bash
cp .env.example .env            # set LLM_API_KEY for the general agent (optional for governance-only)
./enthermes up                  # builds + starts stack; GET /health
curl -s localhost:8080/health | python3 -m json.tool
```

### Governed general agent (real model, "acts like Hermes")

```bash
export TOK="Bearer manager-demo-token"
# Single governed tool call (RBAC + gate + audit)
curl -s -X POST localhost:8080/tools/run -H "Authorization: $TOK" \
  -H 'content-type: application/json' \
  -d '{"org":"acme","tool":"general.status","args":{}}'

# General agent run (LLM tool-calling loop, every call governed/audited)
curl -s -X POST localhost:8080/agents/run -H "Authorization: $TOK" \
  -H 'content-type: application/json' \
  -d '{"org":"acme","prompt":"Plan a small billing service: save a design note, then give me a 3-line summary."}'
```

### Human-in-the-loop gate demo (high-risk tool)

```bash
# high-risk call blocks until approval  -> 409 {request_id}
curl -s -X POST localhost:8080/tools/run -H "Authorization: $TOK" \
  -H 'content-type: application/json' \
  -d '{"org":"acme","tool":"code.run_tests","args":{"cmd":"pytest"}}'
# find the req_id, then approve:
curl -s -X POST localhost:8080/gate/<REQ_ID>/decide?org=acme -H "Authorization: $TOK" \
  -H 'content-type: application/json' -d '{"approver":"manager","approve":true}'
```

### Multi-agent orchestration

```bash
curl -s -X POST localhost:8080/orchestrate/launch -H "Authorization: $TOK" \
  -H 'content-type: application/json' -d '{"org":"acme","task":"Research and summarize the API design"}'
curl -s "localhost:8080/orchestrate/status?job_id=<JOB_ID>&org=acme"
```

### Admin console
Open `http://localhost:8080/admin` — live org status, pending approvals, orchestration runs, audit trail.

## Tests
```bash
./enthermes test          # pytest: audit immutability, RBAC, gates
```

## Compliance
`compliance/` ships SOC 2 / ISO 27001 / GDPR control mappings + evidence templates
(control mapping + evidence templates — conduct your own audit).

## Deployment
```bash
git clone https://github.com/aidendify/aidentify-enterprise-hermes
cd aidentify-enterprise-hermes && cp .env.example .env && ./enthermes up
```
See `runbook/ADMIN_RUNBOOK.md` (deploy, configure SSO, operate, add orgs) and
`security/hardening-checklist.md`.

### Live reference deployment (Hostinger VPS)
`http://200.234.33.118:8081` — governance validated live (health ✓, RBAC 403 ✓,
high-risk gate 409 ✓, immutable audit ✓, admin console ✓). Egress-safe default
(no LLM key shipped to the public container); supply `LLM_API_KEY` in the host
`.env` to enable general agents.

*Governed, not guessed. Run autonomous agents inside your firewall.*