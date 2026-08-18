"""Agent orchestration engine.

Queue tasks, then execute them with the full governance stack wrapped around
every tool call:

    Authenticate principal -> RBAC scope check -> tool allowlist check ->
    risk routing (human-approval gate for high-risk) -> execute -> audit.

This is the "governed autonomy" control loop that distinguishes the private
enterprise platform from a raw chat wrapper.
"""
from __future__ import annotations

from collections import deque
from typing import Any, Callable

from .audit import AuditLog
from .auth import Principal, RBAC
from .gates import ApprovalRequired, Gate
from .tools import ToolRegistry


class Task:
    def __init__(self, tool_name: str, args: dict, principal: Principal, req_id: str | None = None):
        self.tool_name = tool_name
        self.args = args
        self.principal = principal
        self.req_id = req_id


class AgentRuntime:
    def __init__(
        self,
        registry: ToolRegistry,
        rbac: RBAC,
        audit: AuditLog,
        gate: Gate,
        allow_egress: bool = False,
    ):
        self.registry = registry
        self.rbac = rbac
        self.audit = audit
        self.gate = gate
        self.allow_egress = allow_egress

    def execute(self, task: Task) -> dict:
        tool = self.registry.get(task.tool_name)          # allowlist enforcement
        principal: Principal = task.principal
        if not principal.can(tool.scope):                 # RBAC enforcement
            self.audit.append("rbac/denied", principal.user_id,
                              {"tool": tool.name, "scope": tool.scope, "role": principal.role.name})
            raise PermissionError(f"role '{principal.role.name}' cannot use scope '{tool.scope}'")

        # High risk => force human approval gate before execution.
        if tool.risk == "high":
            if not task.req_id:
                raise ApprovalRequired(
                    self.gate.request(principal.user_id, tool.name, task.args,
                                      approvers=["manager"])
                )
            self.gate.resolve(task.req_id)                # raises if pending/denied

        handler = tool.handler or self._noop
        try:
            result = handler(**task.args) if handler is not self._noop else self._noop(**task.args)
            outcome = "ok"
            if isinstance(result, dict) and result.get("ok") is False:
                outcome = "error"
        except Exception as exc:                          # noqa: BLE001
            result = {"ok": False, "error": str(exc)}
            outcome = "error"

        self.audit.append("tool/exec", principal.user_id, {
            "tool": tool.name, "risk": tool.risk, "args": task.args,
            "outcome": outcome, "result": str(result)[:500],
        })
        return result

    def execute_webreq(self, tool_name: str, args: dict, principal: Principal,
                       req_id: str | None = None) -> dict:
        """Convenience entry point used by the web API, the agent driver, and the
        orchestrator. Same governance path as execute(); for high-risk tools pass
        a pre-approved req_id to proceed, or omit it to trigger the gate."""
        return self.execute(Task(tool_name=tool_name, args=args,
                                 principal=principal, req_id=req_id))

    @staticmethod
    def _noop(**kw: Any) -> dict:
        return {"ok": True, "handled": False, "echo": kw}


class TaskQueue:
    def __init__(self, runtime: AgentRuntime):
        self.runtime = runtime
        self._q: deque[Task] = deque()

    def enqueue(self, task: Task) -> int:
        self._q.append(task)
        return len(self._q)

    def run_next(self) -> dict | None:
        if not self._q:
            return None
        return self.runtime.execute(self._q.popleft())

    def size(self) -> int:
        return len(self._q)