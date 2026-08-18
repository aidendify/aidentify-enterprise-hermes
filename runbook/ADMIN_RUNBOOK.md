# Enterprise Agent Ops — Admin Runbook

Deploy, configure, operate, and troubleshoot the self-hosted platform.

## 1. Prerequisites
- A Linux host (or VM/Docker host) inside your network, with `docker` + `docker compose`,
  or Python 3.10+ with `pip`.
- An **in-network** OpenAI-compatible model endpoint (`LLM_BASE_URL`) — e.g. vLLM, Ollama,
  or a private gateway. The core logic works without one for demos/tests.

## 2. Deploy (containers)
```bash
cp .env.example .env           # edit values
# required: LLM_BASE_URL, AUDIT_HMAC_KEY (strong random)
docker compose up -d --build
curl -s localhost:8080/health   # -> {"status":"ok",...}
```

## 3. Deploy (bare metal / non-container)
```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
python3 scripts/demo.py         # verify the governed core
uvicorn api.main:app --host 0.0.0.0 --port 8080
```

## 4. Configure
- **SSO:** set `OIDC_ISSUER` / `SAML_IDP_METADATA_URL`; wire a verifier in
  `core/auth.py`. Remove demo tokens.
- **Roles:** edit `config/entitlements.yaml` (scopes per role).
- **Tools:** edit `config/tools.yaml` (risk level high ⇒ approval gate).
- **Egress:** keep `ALLOW_EGRESS=false`.

## 5. Operate — common workflows
- Run the demo: `python3 scripts/demo.py`
- Test suite: `python3 scripts/validate_pack.py` or `pytest tests/`
- Check health: `GET /health`
- List pending approvals: `GET /gate/pending`
- Approve a gate: `POST /gate/{id}/decide` `{"approver":"manager","approve":true,"reason":"..."}`
- Read audit: `GET /audit`
- Ship audit to SIEM: use the `GET /audit` reader in a cron pull.

## 6. Troubleshooting
| Symptom | Cause/Fix |
|---------|-----------|
| `/health` 500 | audit chain check failed — restore from backup or re-init (see below) |
| 401 on `/run` | token invalid — set a valid demo token or wire SSO |
| 403 on `/run` | role lacks scope — grant scope in `entitlements.yaml` (least privilege!) |
| 409 on `/run` | high-risk tool awaiting approval — approve via `/gate/.../decide` |
| `code.run_tests` fails | compound scripts blocked by design; use a single safe command |
| audit tamper alert | someone edited `_data/audit.log` — investigate before restore |

## 7. Backup & recovery
- Backup `_data/` (datastore + audit) and `.env` config; audit should be write-once
  and archived. Restore datastore from backup; keep audit as a chain (replay from the
  backup, not a re-write).
- Rotate `AUDIT_HMAC_KEY` on a schedule; verify chain with `AuditLog.verify()`.

## 8. Security hygiene (see `security/hardening-checklist.md`)
- Non-root runtime, reverse-proxy TLS, network isolation, no secrets in git,
  red-team test RBAC denials.

## 9. Customising agents / tools
1. Add a handler + `Tool` in `core/tools.py` (set risk).
2. Declare scope in `config/entitlements.yaml`.
3. (Optional) wrap a workflow in `agents/` like the existing five.
4. Re-run `scripts/validate_pack.py` to confirm nothing broke.