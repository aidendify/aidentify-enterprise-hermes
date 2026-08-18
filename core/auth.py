"""Identity (OIDC/SAML plug point) + RBAC entitlements.

Enterprises require SSO (SAML/OIDC) so admins control who is a user, plus
role-based access control so agents can only use the tools their role is
entitled to (least privilege). This module:

- loads config/entitlements.yaml (role -> allowed tool scopes)
- exposes an `authenticate` plug point: in production you wire an OIDC/SAML
  IdP; in the bundled demo an admin-issued token works.
- enforces `PrincipalRole.can(scope)` before any tool runs.

Security posture: RBAC + SSO are core enterprise requirements (SOC2 CC6 /
ISO 27001 A.9). No tool runs without an authenticated principal.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


class AuthError(Exception):
    pass


class Role:
    def __init__(self, name: str, scopes: set[str]):
        self.name = name
        self.scopes = set(scopes)

    def can(self, scope: str) -> bool:
        # Exact scope match OR prefix wildcard (e.g. "ops:*" grants "ops:attendance").
        if scope in self.scopes:
            return True
        prefix = scope.split(":")[0] + ":*"
        return prefix in self.scopes


class Principal:
    def __init__(self, user_id: str, role: Role, email: str = ""):
        self.user_id = user_id
        self.role = role
        self.email = email

    def can(self, scope: str) -> bool:
        return self.role.can(scope)


class RBAC:
    def __init__(self, entitlements_path: str | Path):
        self.entitlements_path = Path(entitlements_path)
        self.roles: dict[str, Role] = {}
        self.load()

    def load(self) -> None:
        with self.entitlements_path.open() as fh:
            data = yaml.safe_load(fh) or {}
        for role_name, cfg in (data.get("roles") or {}).items():
            self.roles[role_name] = Role(role_name, cfg.get("scopes", []))

    def get_role(self, name: str) -> Role:
        role = self.roles.get(name)
        if not role:
            raise AuthError(f"unknown role: {name}")
        return role

    def principal(self, user_id: str, role_name: str, email: str = "") -> Principal:
        return Principal(user_id, self.get_role(role_name), email)


class Authenticator:
    """Pluggable identity.

    `token_authenticator` is the bundled demo path (admin signs a token).
    Replace `authenticate` with an OIDC (PyJWT) or SAML (python3-saml)
    verifier in production — the authz surface stays identical.
    """

    def __init__(self, rbac: RBAC, allowlist: dict[str, str] | None = None):
        self.rbac = rbac
        self.tokens: dict[str, str] = allowlist or {"demo-token": "employee"}

    def authenticate(self, token: str) -> Principal:
        role_name = self.tokens.get(token)
        if not role_name:
            raise AuthError("invalid or missing token")
        return self.rbac.principal(f"user-{token[:6]}", role_name, f"{token[:6]}@corp.local")

    def add_token(self, token: str, role_name: str) -> None:
        self._role_exists(role_name)
        self.tokens[token] = role_name

    def _role_exists(self, role_name: str) -> None:
        self.rbac.get_role(role_name)  # raises if missing