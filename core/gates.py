"""Human-approval gates for high-risk agent actions.

Autonomous agents are powerful; enterprises need a *human in the loop* for
irreversible or high-risk actions (deployments, payouts, external sends,
system changes). This gate holds a request in `pending` state and only
executes when an authorized approver records a decision. Both approval and
denial are written to the immutable audit log.

Security posture: recorded human sign-off on risky tool calls is the core
of the "governed autonomy" promise (SOC2 CC8 change/exception controls).
"""
from __future__ import annotations

import time
import uuid


class ApprovalRequired(Exception):
    def __init__(self, req_id: str, message: str = ""):
        super().__init__(message)
        self.request_id = req_id


class ApprovalDenied(Exception):
    pass


class Gate:
    def __init__(self, audit):
        self.audit = audit
        self._pending: dict[str, dict] = {}

    def request(self, actor: str, action: str, payload: dict, approvers: list[str]) -> str:
        req_id = str(uuid.uuid4())
        self._pending[req_id] = {
            "req_id": req_id,
            "actor": actor,
            "action": action,
            "payload": payload,
            "approvers": approvers,
            "status": "pending",
            "ts": time.time(),
        }
        self.audit.append("gate/request", actor, {
            "req_id": req_id, "action": action, "payload": payload,
        })
        return req_id

    def decide(self, req_id: str, approver: str, approve: bool, reason: str = "") -> dict:
        req = self._pending.get(req_id)
        if not req:
            raise ApprovalDenied(f"unknown request: {req_id}")
        if approver not in req["approvers"]:
            raise ApprovalDenied(f"{approver} is not an approver for {req_id}")
        req["status"] = "approved" if approve else "denied"
        req["decided_by"] = approver
        req["reason"] = reason
        req["decided_at"] = time.time()
        self.audit.append(
            "gate/decision",
            approver,
            {"req_id": req_id, "action": req["action"], "approve": approve, "reason": reason},
        )
        return req

    def resolve(self, req_id: str) -> dict:
        """Return the decision; raise if still pending or denied."""
        req = self._pending[req_id]
        if req["status"] == "pending":
            raise ApprovalRequired(req_id, "awaiting human approval")
        if req["status"] == "denied":
            raise ApprovalDenied(f"denied: {req.get('reason', '')}")
        return req

    def pending_list(self) -> list[dict]:
        return [r for r in self._pending.values() if r["status"] == "pending"]