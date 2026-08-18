"""Tests for the immutable audit log."""
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.audit import AuditError, AuditLog          # noqa: E402


def _tmp_path(tag: str) -> str:
    d = Path(tempfile.mkdtemp(prefix="ea_audit_"))
    return str(d / f"{tag}.log")


def test_append_and_read():
    aud = AuditLog(_tmp_path("a"))
    aud.append("test/event", "alice", {"a": 1})
    recs = aud.read("test/event")
    assert any(r["actor"] == "alice" for r in recs)
    assert aud.verify() is True


def test_chain_linkage():
    aud = AuditLog(_tmp_path("b"))
    aud.append("a", "u1", {})
    aud.append("b", "u2", {})
    lines = aud.path.read_text().strip().splitlines()
    recs = [__import__("json").loads(l) for l in lines]
    assert recs[1]["prev"] == recs[0]["hash"]  # chained
    assert recs[1]["seq"] == recs[0]["seq"] + 1


def test_tamper_detected():
    aud = AuditLog(_tmp_path("c"))
    aud.append("x", "u", {})
    lines = aud.path.read_text().strip().splitlines()
    lines.insert(1, lines[0])  # duplicate a line -> prev mismatch on next
    aud.path.write_text("\n".join(lines) + "\n")
    try:
        aud.verify()
        assert False, "tamper not detected"
    except AuditError:
        assert True


if __name__ == "__main__":
    for fn in [test_append_and_read, test_chain_linkage, test_tamper_detected]:
        fn()
        print(f"PASS {fn.__name__}")