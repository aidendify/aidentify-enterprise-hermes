# Enterprise-Hermes — Delivery & Next Steps

## What you got
A governed, self-hosted **general** agent appliance built on the MIT-licensed
Hermes Agent engine — the enterprise version of `enterprise-agent-ops` (which
shipped 5 canned workflows; this ships a real general agent, wrapped in the
same governance).

**Repository:** https://github.com/aidendify/aidentify-enterprise-hermes
**PRD:** `prds/PRD-enterprise-hermes-20260818.md`
**Local working copy:** `products/enterprise-hermes/`

## What's included
- **Governance shell** — SSO/RBAC (OIDC/SAML plug point), immutable HMAC audit,
  human-approval gates, least-privilege tool allowlist, **zero data egress by default**
- **Hermes engine (vendored, MIT)** — general agent loop, provider-agnostic LLM,
  tools, skills, memory, orchestration
- **Multi-org control plane** — per-org isolation, admin web console, org provisioning
- **Orchestration** — concurrent workstreams + multi-agent delegation
- **Appliance** — `./enthermes up`, Docker + compose, compliance & security packs

## Verified
- 10/10 governance unit tests pass (audit / rbac / gates)
- End-to-end validated with a real model (OpenRouter): the agent performed
  governed tool calls (wrote a design note, queried status), every action audited
  → ✓ "acts like Hermes"
- Orchestration: launched workstream + delegated subtask, both completed
- **Live on Hostinger VPS:** http://200.234.33.118:8081
  (health ✓ · RBAC 403 ✓ · high-risk gate 409 ✓ · audit trail ✓ · admin console ✓)

## Next steps (propose to founder)
1. **Gate approval recorded** for publish/promo before listing → Gumroad $99 SKU
   (free self-host + managed-hosting upsell), matching enterprise-agent-ops listing pattern.
2. Enable live model on the hosted instance by supplying an `LLM_API_KEY`
   to the host `.env` (the public container intentionally stays zero-egress).
3. (Later) Stage 2 — clean-room general agent core to own the engine IP.
4. Update `reports/kaizen_log.md` + `products_snapshot.json` once a gate is approved.

## Pricing (PRD proposal)
- **$99** self-host (free self-host demo SKU + premium managed-hosting / multi-node later).
- Differentiator: genuinely general agent + governance + zero egress, MIT-legal.