"""Tests for human-approval gates."""
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.audit import AuditLog                       # noqa: E402
from core.gates import ApprovalDenied, ApprovalRequired, Gate  # noqa: E402


def _gate():
    d = Path(tempfile.mkdtemp(prefix="ea_gate_"))
    return Gate(AuditLog(str(d / "gate.log")))


def test_request_then_pending():
    g = _gate()
    rid = g.request("alice", "code.run_tests", {"cmd": "x"}, approvers=["mgr"])
    assert g.pending_list()[0]["status"] == "pending"
    try:
        g.resolve(rid)
        assert False, "should be pending"
    except ApprovalRequired:
        assert True


def test_approve_then_resolve():
    g = _gate()
    rid = g.request("alice", "code.run_tests", {}, approvers=["mgr"])
    g.decide(rid, "mgr", True, "ok")
    assert g.resolve(rid)["status"] == "approved"


def test_deny_raises():
    g = _gate()
    rid = g.request("alice", "payments.send", {}, approvers=["cfo"])
    g.decide(rid, "cfo", False, "not authorized")
    try:
        g.resolve(rid)
        assert False, "should be denied"
    except ApprovalDenied:
        assert True


def test_non_approver_rejected():
    g = _gate()
    rid = g.request("alice", "x", {}, approvers=["mgr"])
    try:
        g.decide(rid, "intruder", True)
        assert False, "non-approver accepted"
    except ApprovalDenied:
        assert True


if __name__ == "__main__":
    for fn in [test_request_then_pending, test_approve_then_resolve, test_deny_raises, test_non_approver_rejected]:
        fn()
        print(f"PASS {fn.__name__}")