# Hardening Checklist — Enterprise Agent Ops

Use as a tenant-deployment checklist. Each item maps to a security control; the
compliance matrices in `compliance/` reference these.

## Identity & access
- [ ] Replace demo tokens with real SSO (OIDC or SAML) in `.env` (`OIDC_ISSUER`,
      `SAML_IDP_METADATA_URL`); verify `core/auth.py` now uses the IdP verifier.
- [ ] Enforce MFA on the IdP for all privileged roles.
- [ ] Review `config/entitlements.yaml`: grant roles the *least* scopes needed.
- [ ] Remove all demo tokens from `Authenticator.allowlist` before production.
- [ ] Integrate SCIM for automated user provisioning/deprovisioning offboarding.

## Data protection
- [ ] Keep `ALLOW_EGRESS=false`; verify no outbound model/tool endpoint is referenced.
- [ ] Point `LLM_BASE_URL` at an in-network / in-region endpoint (data residency).
- [ ] Encrypt `AUDIT_LOG` at rest; protect `AUDIT_HMAC_KEY` (KMS/vault, not env).
- [ ] Encrypt datastore volumes (see `docker-compose.yml` volume encryption).
- [ ] Configure retention/rotation for datastore + audit per policy.

## Audit & monitoring
- [ ] Ship audit records to enterprise SIEM (Splunk/Elastic) via the audit reader.
- [ ] Verify `AuditLog.verify()` runs on a schedule (tamper detection).
- [ ] Alert on: approval denials, RBAC denials, any `ALLOW_EGRESS` change.
- [ ] Review approval-gate queue daily (`/gate/pending`).

## Tool & network hygiene
- [ ] Curate `config/tools.yaml`: only allow tools you need; set risk correctly.
- [ ] Run the API and agents behind a reverse proxy with TLS (e.g. nginx/Caddy).
- [ ] Network-isolate the agent sandbox (no internet route; DB + model only).
- [ ] Apply OS-level least privilege — run agents as non-root, read-only filesystem
      where possible, `no_new_privs`.

## Secrets
- [ ] No secrets committed. Use vault/KMS; `.env` file permissions `600`.
- [ ] Rotate `AUDIT_HMAC_KEY` and any API tokens on a schedule.

## Verification
- [ ] `python3 scripts/validate_pack.py` passes.
- [ ] Red-team test: an `employee` token cannot call a `manager` scope (expect 403).
- [ ] Confirm a tamper in `_data/audit.log` is caught by `AuditLog.verify()`.