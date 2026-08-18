# Threat Model — Enterprise Agent Ops

## In scope
Self-hosted single-org deployment behind the firewall. Intended trust boundary:
the tenant's network + identity infrastructure.

## Assets
- **Audit log** (`_data/audit.log`) — integrity and availability critical.
- **Datastore** (`agents/store.py`, `_data/`) — attendance, tasks, activity records.
- **Tool registry** (`core/tools.py`) — code execution risk.
- **Principal entitlements** (`config/entitlements.yaml`).
- **Secrets** (`AUDIT_HMAC_KEY`, tokens, `.env`).

## Threat actors
- Unauthenticated attacker (external).
- Insider employee (least-privilege evader).
- Malicious/compromised agent tool / prompt injection.
- Auditor/regulator (needs reliable evidence).

## Threats, mitigations

| # | Threat | Likelihood | Impact | Mitigation (where enforced) |
|---|--------|-----------|--------|------------------------------|
| T1 | Unauthenticated tool access | Medium | High | `core/auth.py` — every call requires a valid principal; API returns 401 without token. |
| T2 | Privilege escalation (employee → manager scope) | Medium | High | `core/auth.py` RBAC + `core/task_queue.py` scope check before every tool; denies logged. |
| T3 | Promiscuous/unknown tool invocation | Medium | High | `core/tools.py` allowlist registry — unknown tool name raises `ToolError`. |
| T4 | High-risk action with no human sign-off | High | High | `core/gates.py` — high-risk tools hold at approval gate; no execution without decision. |
| T5 | Audit tampering / log rewriting | Medium | High | `core/audit.py` — HMAC-chained append-only; `verify()` detects any break. |
| T6 | Data egress to unauthorized model/tool | Medium | High | `.env` `ALLOW_EGRESS=false` default; in-network `LLM_BASE_URL` enforced. |
| T7 | Code injection via `code.run_tests` | Medium | High | `core/tools.py` blocks `; && |` compound commands; high-risk ⇒ approval gate; runs in isolated cwd. |
| T8 | Denial of service on ingestion | Low | Medium | Rate-limit API; isolate DB. |
| T9 | Secret leakage in logs | Medium | High | `.env.example` only; secrets via vault; audit payloads truncated (`[:500]`). |

## Residual risks
- The approval gate relies on a human decision being recorded; a **compromised or
  careless approver** is out of scope but auditable (who approved what, when).
- Prompt-injection hardening of LLM-facing agents is additive (see LICENSE —
  product is a self-hosted kit; production hardening is tenant's responsibility).