"""Pack-specific validator — the release/QA check for this product."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

REQUIRED = [
    "README.md", "LICENSE.md", "ACCESS.md",
    "docker-compose.yml", ".env.example",
    "config/entitlements.yaml", "config/tools.yaml",
    "core/audit.py", "core/auth.py", "core/gates.py", "core/tools.py", "core/task_queue.py",
    "agents/attendance.py", "agents/daily_report.py", "agents/access_tracker.py",
    "agents/project_ops.py", "agents/build_test.py",
    "api/main.py", "scripts/demo.py",
    "security/hardening-checklist.md", "security/threat-model.md",
    "compliance/soc2-matrix.md", "compliance/iso27001-matrix.md", "compliance/gdpr-residency.md",
    "runbook/ADMIN_RUNBOOK.md",
    "tests/test_audit.py", "tests/test_rbac.py", "tests/test_gates.py",
]


def main() -> int:
    missing = [p for p in REQUIRED if not (ROOT / p).exists()]
    if missing:
        print("MISSING:")
        for m in missing:
            print("  -", m)
        return 1

    # Run the bundled unit tests by exec-ing each test module main.
    sys.path.insert(0, str(ROOT))
    fails = []
    for t in ["test_audit", "test_rbac", "test_gates"]:
        path = ROOT / "tests" / f"{t}.py"
        ns = {"__file__": str(path), "__name__": "validate_pack"}
        exec(compile(path.read_text(), str(path), "exec"), ns)
        for name in list(ns):
            if name.startswith("test_"):
                try:
                    ns[name]()
                except Exception as exc:  # noqa: BLE001
                    fails.append(f"{t}.{name}: {exc}")
    if fails:
        print("UNIT FAILURES:")
        for f in fails:
            print("  -", f)
        return 2

    print("PACK VALIDATOR OK: all required files present; unit tests pass.")
    return 0


if __name__ == "__main__":
    sys.exit(main())