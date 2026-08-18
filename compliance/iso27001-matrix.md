# ISO/IEC 27001:2022 Control Mapping — Enterprise Agent Ops

Maps to Annex A controls. **Evidence template, not certification** — yes, you
really do need the cert firm for the cert; this gives you the evidence.

| ISO 27001 Annex A | Control name | Platform capability |
|-------------------|--------------|---------------------|
| A.5.15 | Access control | RBAC + SSO; per-tool scope checks |
| A.5.16 | Identity management | OIDC/SAML plug point in `core/auth.py` |
| A.8.2 | Information classification | `.env` + secrets via vault; data residency note |
| A.8.12 | Data leakage prevention | `ALLOW_EGRESS=false`; in-network `LLM_BASE_URL` |
| A.8.15 | Logging | Append-only audit log, HMAC-chained |
| A.8.16 | Monitoring activities | Audit reader → SIEM; alert on deny/approve |
| A.5.25 | Assessment of security events | Approval-gate queue review; RBAC denial alerts |
| A.5.28 | Secure coding | Tool allowlist registry; compound-script blocking |
| A.7.10 | Backup | Backup `_data/` + rotate audit (see runbook) |

## What to add for a full audit
- Formal ISMS policies, internal audit schedule, evidence of operating review.
- Encryption key management (KMS) and patch-management records.
- An independent third-party penetration test report.