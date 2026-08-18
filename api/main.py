"""Enterprise-Hermes API — governed agent gateway + admin control plane.

One service exposing:
  /health                  liveness + audit chain verify
  /agents/run              general governed agent (real LLM via LLM_* env)
  /tools/run               single governed tool call (RBAC + gate + audit)
  /tools/allowlist         tool registry (least privilege)
  /orgs/*                  admin: provision/disable orgs (multi-tenancy)
  /audit                   immutable audit trail (role-gated)
  /gate/*                  human-approval queue + decisions
  /orchestrate/*           multi-agent launch/delegate/status
  /admin                   web control plane (static)

Entrypoint: uvicorn api.main:app --host 0.0.0.0 --port 8080
Egress-safe by default: agents talk only to LLM_BASE_URL (in-network).
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from core.audit import AuditLog
from core.auth import Authenticator, AuthError, RBAC
from core.gates import ApprovalRequired, Gate
from core.tools import ToolRegistry
from core.task_queue import AgentRuntime
from agent.hermes_agent import run_governed_agent, DEFAULT_MODEL, DEFAULT_BASE_URL
from orchestration.orchestrator import Orchestrator
from orchestration.orchestrator import AgentRun

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "_data"
DATA.mkdir(exist_ok=True)
ORGS_FILE = DATA / "orgs.json"

LLM_API_KEY = os.environ.get("LLM_API_KEY", "")
LLM_BASE_URL = os.environ.get("LLM_BASE_URL", DEFAULT_BASE_URL)
LLM_MODEL = os.environ.get("LLM_MODEL", DEFAULT_MODEL)
ALLOW_EGRESS = os.environ.get("ALLOW_EGRESS", "false").lower() in ("1", "true", "yes")

app = FastAPI(title="Enterprise-Hermes", version="1.0.0")
app.mount("/web", StaticFiles(directory=str(ROOT / "web")), name="web")


# ----------------------------------------------------------------------
# Multi-tenant org registry
# ----------------------------------------------------------------------
def _load_orgs() -> dict:
    if ORGS_FILE.exists():
        try:
            return json.loads(ORGS_FILE.read_text())
        except json.JSONDecodeError:
            return {}
    return {}


def _save_orgs(orgs: dict) -> None:
    ORGS_FILE.write_text(json.dumps(orgs, indent=2))


_orgs = _load_orgs()
if not _orgs:
    _orgs = {
        "acme": {
            "name": "Acme Demo Corp", "enabled": True,
            "demo_tokens": ["operator-demo-token", "manager-demo-token"],
            "created_at": "2026-08-18",
        }
    }
    _save_orgs(_orgs)


# ----------------------------------------------------------------------
# Per-org governance stacks
# ----------------------------------------------------------------------
class OrgStack:
    def __init__(self, org: str, workspace: Path):
        self.org = org
        self.workspace = workspace
        workspace.mkdir(parents=True, exist_ok=True)
        self.audit = AuditLog(str(workspace / "audit.log"))
        self.rbac = RBAC(ROOT / "config" / "entitlements.yaml")
        self.gate = Gate(self.audit)
        self.registry = ToolRegistry()
        self.auth = Authenticator(self.rbac, allowlist={
            "employee-demo-token": "employee",
            "operator-demo-token": "operator",
            "manager-demo-token": "manager",
        })
        self.runtime = AgentRuntime(self.registry, self.rbac, self.audit,
                                    self.gate, allow_egress=ALLOW_EGRESS)


def _stacks() -> dict[str, OrgStack]:
    stacks = {}
    for org, cfg in _orgs.items():
        ws = DATA / org
        stacks[org] = OrgStack(org, ws)
    return stacks


STACKS: dict[str, OrgStack] = _stacks()
ORCH = Orchestrator({org: s.runtime for org, s in STACKS.items()})


def _stack(org: str) -> OrgStack:
    st = STACKS.get(org)
    if not st:
        raise HTTPException(404, f"unknown org: {org}")
    if not _orgs.get(org, {}).get("enabled", False):
        raise HTTPException(403, f"org disabled: {org}")
    return st


def _principal(st: OrgStack, org: str, authorization: str):
    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        raise HTTPException(401, "missing bearer token")
    try:
        return st.auth.authenticate(token)
    except AuthError as exc:
        st.audit.append("auth/failed", token[:8], {"org": org, "reason": str(exc)})
        raise HTTPException(401, str(exc)) from exc


def _authz(st: OrgStack, principal, scope: str):
    if not principal.can(scope):
        st.audit.append("rbac/denied", principal.user_id, {"scope": scope})
        raise HTTPException(403, f"role '{principal.role.name}' cannot use scope '{scope}'")


# ----------------------------------------------------------------------
# Request models
# ----------------------------------------------------------------------
class RunRequest(BaseModel):
    org: str = "acme"
    prompt: str


class ToolRequest(BaseModel):
    org: str = "acme"
    tool: str
    args: dict = {}
    request_id: str | None = None  # pre-approved gate req_id (for high-risk tools)


class ApproveRequest(BaseModel):
    approver: str
    approve: bool
    reason: str = ""


class OrgCreate(BaseModel):
    name: str
    slug: str


class OrchestrateRequest(BaseModel):
    org: str = "acme"
    task: str


# ----------------------------------------------------------------------
# Public gateway
# ----------------------------------------------------------------------
@app.get("/health")
def health():
    ok = []
    for org, st in STACKS.items():
        st.audit.verify()
        ok.append({"org": org, "tools": len(st.registry.allowlist()),
                   "enabled": _orgs[org]["enabled"]})
    return {"status": "ok", "orgs": ok, "allow_egress": ALLOW_EGRESS,
            "llm_base_url": LLM_BASE_URL, "llm_model": LLM_MODEL}


@app.get("/tools/allowlist")
def allowlist(org: str = "acme"):
    st = _stack(org)
    return {"org": org, "tools": st.registry.allowlist()}


@app.post("/tools/run")
def tool_run(req: ToolRequest, authorization: str = Header(default="")):
    st = _stack(req.org)
    principal = _principal(st, req.org, authorization)
    try:
        result = st.runtime.execute_webreq(req.tool, req.args, principal,
                                           req_id=req.request_id)
        return {"result": result}
    except PermissionError as exc:
        raise HTTPException(403, str(exc)) from exc
    except ApprovalRequired as areq:
        raise HTTPException(409, {"request_id": areq.request_id,
                                  "message": str(areq)}) from areq


# -- governed general agent (the "acts like Hermes" path) -----------------
@app.post("/agents/run")
def agent_run(req: RunRequest, authorization: str = Header(default="")):
    st = _stack(req.org)
    principal = _principal(st, req.org, authorization)
    _authz(st, principal, "general")  # general agent requires general scope
    if not ALLOW_EGRESS and not LLM_API_KEY:
        raise HTTPException(503, "LLM not configured (set LLM_API_KEY in .env); "
                                  "and ALLOW_EGRESS=false by default")
    try:
        return run_governed_agent(
            st.runtime, req.prompt, principal,
            api_key=LLM_API_KEY, base_url=LLM_BASE_URL, model=LLM_MODEL,
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(502, f"agent error: {exc}") from exc


# ----------------------------------------------------------------------
# Audit (role-gated)
# ----------------------------------------------------------------------
@app.get("/audit")
def audit(org: str = "acme", event: str | None = None,
          authorization: str = Header(default="")):
    st = _stack(org)
    principal = _principal(st, org, authorization)
    if not (principal.can("audit:read") or principal.can("ops:reports")):
        _authz(st, principal, "audit:read")
    return {"org": org, "records": st.audit.read(event)}


# ----------------------------------------------------------------------
# Human-approval gates
# ----------------------------------------------------------------------
@app.get("/gate/pending")
def gate_pending(org: str = "acme", authorization: str = Header(default="")):
    st = _stack(org)
    _principal(st, org, authorization)
    return {"org": org, "pending": st.gate.pending_list()}


@app.post("/gate/{req_id}/decide")
def gate_decide(req_id: str, req: ApproveRequest, org: str = "acme",
                authorization: str = Header(default="")):
    st = _stack(org)
    _principal(st, org, authorization)
    try:
        return {"decision": st.gate.decide(req_id, req.approver,
                                           req.approve, req.reason)}
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(400, str(exc)) from exc


# ----------------------------------------------------------------------
# Orchestration (multi-agent)
# ----------------------------------------------------------------------
@app.post("/orchestrate/launch")
def orch_launch(req: OrchestrateRequest, authorization: str = Header(default="")):
    st = _stack(req.org)
    principal = _principal(st, req.org, authorization)
    _authz(st, principal, "general")
    run: AgentRun = ORCH.launch(req.org, req.task, principal)
    return {"job_id": run.job_id}


@app.post("/orchestrate/delegate")
def orch_delegate(req: OrchestrateRequest, parent_job_id: str,
                  authorization: str = Header(default="")):
    st = _stack(req.org)
    principal = _principal(st, req.org, authorization)
    _authz(st, principal, "general")
    sub = ORCH.delegate(req.org, parent_job_id, req.task, principal)
    return {"sub_job_id": sub.job_id, "parent_job_id": parent_job_id}


@app.get("/orchestrate/status")
def orch_status(job_id: str, org: str = "acme"):
    run = ORCH.status(job_id)
    if not run:
        raise HTTPException(404, "unknown job")
    return run.to_dict()


@app.get("/orchestrate/runs")
def orch_runs(org: str = "acme"):
    return {"runs": ORCH.list_runs(org)}


# ----------------------------------------------------------------------
# Admin control plane
# ----------------------------------------------------------------------
@app.get("/admin")
def admin_ui():
    return FileResponse(ROOT / "web" / "index.html")


@app.get("/admin/overview")
def admin_overview():
    return {"orgs": _orgs, "runs": ORCH.list_runs()}