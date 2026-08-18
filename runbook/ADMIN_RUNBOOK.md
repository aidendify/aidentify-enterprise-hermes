# Enterprise-Hermes — Admin Runbook

Deploy, configure SSO, operate, and maintain a governed Enterprise-Hermes
appliance. This is the operator guide for the *governance + control plane*;
the Hermes engine internals are the upstream project's domain.

## 1. Deploy

### One-command (Docker host with docker + compose)
```bash
git clone https://github.com/aidendify/aidentify-enterprise-hermes
cd aidentify-enterprise-hermes
cp .env.example .env          # set LLM_* (in-network endpoint + key) for the agent engine
./enthermes up                # build + boot on http://<host>:8081
curl -s localhost:8081/health | python3 -m json.tool
```

### Admin console
Open `http://<host>:8081/admin` — org status, pending approvals, orchestration
runs, and the immutable audit trail.

### (Hostinger Docker manager)
Deploy the repo via `POST /docker {project_name, content: <git url>}`, then run
the project's `/start` (the runner creates a container first; start it after).
The compose maps host `8081 → container 8080`.

## 2. Test the delivered logic
```bash
./enthermes test            # governance unit tests (audit / rbac / gates)
bash scripts/e2e.sh         # gate-approval flow + general agent smoke (needs LLM_API_KEY)
```

## 3. Connect the real agent engine (LLM)
The platform is egress-safe by default: with no `LLM_API_KEY` configured, all
governance works and `/agents/run` returns HTTP 503. To enable general agents:

```bash
# in .env on the host:
LLM_BASE_URL=https://your-in-network-endpoint/v1   # keep in-network for zero egress
LLM_MODEL=your-model
LLM_API_KEY=...                                   # real key — never commit
ALLOW_EGRESS=false                                # stays false = safe default
```
Then `./enthermes up`.

## 4. Enterprise SSO (production)
Replace the demo token authenticator in `core/auth.py` (`Authenticator`) with a
real **OIDC** (PyJWT) or **SAML** (python3-saml) verifier wired to your IdP.
The RBAC surface (`Principal.can(scope)`) is unchanged. Rotate/remove all
`*-demo-token` values.

## 5. Adding a tenant org
```bash
./scripts/provision_org.sh <client-slug> "Client Name"
```
Each org gets an isolated Hermes profile workspace + audit chain under `_data/<slug>/`.

## 6. Multi-agent orchestration
`POST /orchestrate/launch` starts a governed agent workstream; `POST
/orchestrate/delegate` fans out subtasks; `GET /orchestrate/status` and
`GET /orchestrate/runs` report progress. Every subtask routes through the same
RBAC / gate / audit as interactive runs.

## 7. Key security notes
- **Zero egress by default** — agents talk only to `LLM_BASE_URL`. Keep it
  in-network; never set `ALLOW_EGRESS=true` unless you have an explicit,
  audited reason.
- **Immutable audit** — every tool call and approval is HMAC-chained. Back up
  `_data/<org>/audit.log`; verify integrity with the `AuditLog.verify()` method.
- **Human gates** — `risk: high` tools block until an authorized approver signs
  off. Audit the reason.
- **Least privilege** — grant scopes in `config/entitlements.yaml`; never give a
  role more than it needs.

## 8. Troubleshooting
- `/health` not OK → check the container is started (`docker compose ps`);
  confirm `/admin` renders (service is up).
- `/agents/run` → 503 → `LLM_API_KEY` not set (see §3).
- Tool returns `rbac/denied` → role lacks the scope in `entitlements.yaml`.
- Tool returns `gate_required` (409) → approve via admin console (`/gate/pending`)
  or `POST /gate/<req_id>/decide` then retry with `request_id`.