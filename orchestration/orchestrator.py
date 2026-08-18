"""Multi-agent orchestration for Enterprise-Hermes.

Provides the 'orchestration inside it' capability: run concurrent governed agent
workstreams per org, delegate subtasks between agents, and merge results into a
shared org workspace. Every agent run funnels through the same governance path
(runtime.execute_webreq) so RBAC / gates / audit apply to every agent.

This is a reference orchestration layer: real Hermes deployments get the fuller
delegate/spawn/cron engine under the hood; this module proves the governed
orchestration loop and is what the admin console drives.
"""
from __future__ import annotations

import concurrent.futures
import threading
import time
import uuid
from typing import Callable

from core.auth import Principal
from core.task_queue import AgentRuntime
from agent.hermes_agent import run_governed_agent

AgentFn = Callable[[AgentRuntime, str, Principal, str], dict]


class AgentRun:
    def __init__(self, job_id: str, org: str, task: str, principal: Principal):
        self.job_id = job_id
        self.org = org
        self.task = task
        self.principal = principal
        self.status = "queued"
        self.result: dict | None = None
        self.error: str | None = None
        self.started_at = 0.0
        self.finished_at = 0.0
        self.sub_results: list[dict] = []  # delegated subtask outputs

    def to_dict(self) -> dict:
        return {
            "job_id": self.job_id,
            "org": self.org,
            "task": self.task,
            "status": self.status,
            "result": self.result,
            "error": self.error,
            "sub_results": self.sub_results,
            "elapsed_s": round(self.finished_at - self.started_at, 2) if self.started_at else None,
        }


class Orchestrator:
    def __init__(self, runtime_by_org: dict[str, AgentRuntime],
                 agent_fn: AgentFn = run_governed_agent, max_workers: int = 4):
        self._runtime_by_org = runtime_by_org
        self._agent_fn = agent_fn
        self._runs: dict[str, AgentRun] = {}
        self._lock = threading.Lock()
        self._pool = concurrent.futures.ThreadPoolExecutor(max_workers=max_workers)

    def runtime(self, org: str) -> AgentRuntime:
        rt = self._runtime_by_org.get(org)
        if not rt:
            raise KeyError(f"unknown org: {org}")
        return rt

    # -- public ---------------------------------------------------------
    def launch(self, org: str, task: str, principal: Principal) -> AgentRun:
        run = AgentRun(f"job-{uuid.uuid4().hex[:12]}", org, task, principal)
        with self._lock:
            self._runs[run.job_id] = run
        run.status = "queued"
        self._pool.submit(self._execute, run)
        return run

    def delegate(self, org: str, primary_job_id: str, subtask: str,
                 worker_principal: Principal) -> AgentRun:
        """Spawn a subordinate agent; its result is folded back into the primary run."""
        run = AgentRun(f"sub-{uuid.uuid4().hex[:12]}", org, subtask, worker_principal)
        run.status = "queued"
        self._pool.submit(self._execute, run, primary_job_id)
        return run

    def status(self, job_id: str) -> AgentRun | None:
        with self._lock:
            return self._runs.get(job_id)

    def list_runs(self, org: str | None = None) -> list[dict]:
        with self._lock:
            runs = list(self._runs.values())
        if org:
            runs = [r for r in runs if r.org == org]
        return [r.to_dict() for r in sorted(runs, key=lambda r: r.started_at, reverse=True)]

    # -- internals -------------------------------------------------------
    def _execute(self, run: AgentRun, parent_job_id: str | None = None) -> None:
        run.status = "running"
        run.started_at = time.time()
        try:
            rt = self.runtime(run.org)
            run.result = self._agent_fn(rt, run.task, run.principal)
            run.status = "completed"
        except Exception as exc:  # noqa: BLE001
            run.error = str(exc)
            run.status = "failed"
            run.result = {"final": f"ERROR: {exc}", "tool_calls": []}
        finally:
            run.finished_at = time.time()
        if parent_job_id:
            parent = self._runs.get(parent_job_id)
            if parent:
                parent.sub_results.append(run.to_dict())