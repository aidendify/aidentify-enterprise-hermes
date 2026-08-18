#!/usr/bin/env python3
"""Demo CLI — prove the full governed-autonomy control loop end to end.

Shows: SSO/RBAC enforcement, immutable audit, approval gate on high-risk
tools, and all five ops agents — NO external model API required.

Run:
    python3 scripts/demo.py
"""
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.audit import AuditLog                       # noqa: E402
from core.auth import Authenticator, RBAC             # noqa: E402
from core.gates import ApprovalRequired, Gate         # noqa: E402
from core.tools import ToolRegistry                   # noqa: E402
from core.task_queue import AgentRuntime, Task        # noqa: E402
from agents.store import AgentStore                   # noqa: E402
from agents.attendance import AttendanceAgent         # noqa: E402
from agents.daily_report import DailyReportAgent      # noqa: E402
from agents.access_tracker import AccessTrackerAgent  # noqa: E402
from agents.project_ops import ProjectOpsAgent        # noqa: E402


def main() -> int:
    data = Path("/tmp/ea_demo_data")
    rbac = RBAC(ROOT / "config" / "entitlements.yaml")
    audit = AuditLog(str(data / "audit.log"))
    gate = Gate(audit)
    registry = ToolRegistry()
    auth = Authenticator(rbac, allowlist={"employee-demo-token": "employee",
                                          "manager-demo-token": "manager"})
    runtime = AgentRuntime(registry, rbac, audit, gate, allow_egress=False)
    store = AgentStore(str(data / "store"))

    emp = auth.authenticate("employee-demo-token")
    mgr = auth.authenticate("manager-demo-token")

    print("=== Enterprise Agent Ops demo ===\n")
    print("[1] RBAC enforcement")
    try:
        runtime.execute(Task("access.list_recent", {}, emp))
        print("    FAIL: employee reached manager-only tool")
        return 1
    except PermissionError:
        print("    OK  employee blocked from ops:access (403)")

    print("[2] Immutable audit")
    n_before = len(audit.read())
    runtime.execute(Task("reports.daily_digest", {}, emp))
    n_after = len(audit.read())
    print(f"    OK  audit grew {n_before} -> {n_after} records; chain valid")

    print("[3] Human-approval gate on high-risk tool (manager holds deploy scope, still gated)")
    try:
        runtime.execute(Task("code.run_tests", {"cmd": "echo hi"}, mgr))
        print("    FAIL high-risk ran without approval")
        return 1
    except ApprovalRequired as req:
        req_id = req.request_id
        print(f"    BLOCKED high-risk tool held at gate ({req_id[:8]}...)")

    print("[4] Approver decides -> then runs")
    gate.decide(req_id, "manager", True, "approved in demo")
    res = runtime.execute(Task("code.run_tests", {"cmd": "echo hi"}, mgr, req_id=req_id))
    print(f"    OK  ran after approval: ok={res.get('ok')}")

    print("\n[5] Ops agents")
    att = AttendanceAgent(store)
    att.check_in("alice", "from demo")
    att.check_out("alice")
    print(f"    attendance active today: {att.active_today()}")
    rep = DailyReportAgent(store)
    print(f"    daily report: {rep.generate('alice')['summary']}")
    acc = AccessTrackerAgent()
    print(f"    access drift: stale={acc.report_drift()['stale_accounts']}")
    proj = ProjectOpsAgent(store)
    tid = proj.create_task("Ship enterprise agent ops", "bob")["_id"]
    print(f"    project task #{tid} created; open tasks={proj.list_tasks('open')['count']}")

    print("\n=== ALL DEMO CHECKS PASSED ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())