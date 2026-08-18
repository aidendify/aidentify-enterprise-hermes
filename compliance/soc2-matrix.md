# SOC 2 Control Mapping — Enterprise Agent Ops

Maps platform capabilities to common SOC 2 trust-service criteria to *support*
your audit. This is a **mapping + evidence template**, not a certification.

| Trust category | Criterion (illustrative) | How the platform addresses it | Evidence to gather |
|----------------|--------------------------|-------------------------------|--------------------|
| Security (CC6.1) | Logical/ physical access restricted | SSO + RBAC; every tool call requires principal + scope; demo tokens removed in prod | config/entitlements.yaml; SSH/TLS config; IdP logs |
| Security (CC6.3) | Role-based access least privilege | `core/auth.py` RBAC enforced before each tool; wildcard scopes limited to `ops:*` for managers only | RBAC test results; policy review |
| Change Mgmt (CC8.1) | Changes authorized/tracked | Human-approval `gate` for high-risk tools; approval+denial in audit | gate/decision audit records |
| Integrity (A8.1/A8.2) | Processing complete/accurate, data tamper-proof | HMAC-chained immutable audit log; `verify()` catches tamper | audit.log + verify schedule |
| Confidentiality (A6.1/A6.2) | Confidential info protected | Zero data egress default; in-network `LLM_BASE_URL`; volume encryption | `.env` config; network policy |