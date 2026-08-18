"""Tests for RBAC enforcement."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.auth import RBAC                           # noqa: E402


def test_load_roles():
    rbac = RBAC(ROOT / "config" / "entitlements.yaml")
    assert "employee" in rbac.roles
    assert "manager" in rbac.roles


def test_employee_blocked_from_manager_scope():
    rbac = RBAC(ROOT / "config" / "entitlements.yaml")
    emp = rbac.principal("u1", "employee")
    assert emp.can("ops:attendance")      # allowed
    assert not emp.can("ops:access")      # blocked (manager-only)
    assert not emp.can("ops:deploy")      # blocked


def test_manager_wildcard():
    rbac = RBAC(ROOT / "config" / "entitlements.yaml")
    mgr = rbac.principal("u2", "manager")
    assert mgr.can("ops:attendance")
    assert mgr.can("ops:access")
    assert mgr.can("ops:deploy")          # wildcard ops:* + explicit


if __name__ == "__main__":
    for fn in [test_load_roles, test_employee_blocked_from_manager_scope, test_manager_wildcard]:
        fn()
        print(f"PASS {fn.__name__}")