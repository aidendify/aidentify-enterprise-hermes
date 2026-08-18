"""Tool registry with least-privilege risk levels.

Every capability the agents can invoke is declared here with a `risk` level
(low | medium | high) and a required role scope. The runtime refuses to call
anything not in the registry, and `high`-risk tools are routed through the
human-approval gate (core/gates.py) before execution.

Entitlements live in config/entitlements.yaml (RBAC: role -> tool scopes).
Security posture: least-privilege tool access + explicit allowlist — the
antidote to the ungoverned cloud-AI shadow-tool problem.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable


@dataclass
class Tool:
    name: str
    scope: str           # e.g. "ops:attendance"
    risk: str            # low | medium | high
    handler: Callable[..., Any] | None = None
    description: str = ""


class ToolError(Exception):
    pass


class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, Tool] = {}
        self._register_builtins()

    def _register_builtins(self):
        self.register(
            Tool(
                name="attendance.check_in",
                scope="ops:attendance",
                risk="medium",
                handler=self._std,
                description="Record employee check-in.",
            )
        )
        self.register(
            Tool(
                name="attendance.check_out",
                scope="ops:attendance",
                risk="medium",
                handler=self._std,
                description="Record employee check-out.",
            )
        )
        self.register(
            Tool(
                name="reports.daily_digest",
                scope="ops:reports",
                risk="low",
                handler=self._std,
                description="Synthesize daily activity report.",
            )
        )
        self.register(
            Tool(
                name="access.list_recent",
                scope="ops:access",
                risk="medium",
                handler=self._std,
                description="List recent login/access events and flag drift.",
            )
        )
        self.register(
            Tool(
                name="project.create_task",
                scope="ops:project",
                risk="low",
                handler=self._std,
                description="Create a project task.",
            )
        )
        self.register(
            Tool(
                name="code.run_tests",
                scope="ops:deploy",
                risk="high",
                handler=self._run_tests,
                description="Run a repository test command. Args: cmd (string), cwd (string, optional).",
            )
        )
        # --- general-purpose enterprise tools (make the agent *general*) ---
        self.register(
            Tool(
                name="general.plan",
                scope="general",
                risk="low",
                handler=self._plan,
                description="Record a task plan / architecture decision to the org workspace. Args: title (string), detail (string).",
            )
        )
        self.register(
            Tool(
                name="notes.save",
                scope="general",
                risk="medium",
                handler=self._save_note,
                description="Persist a note into the org workspace. Args: filename (string), content (string).",
            )
        )
        self.register(
            Tool(
                name="general.status",
                scope="general",
                risk="low",
                handler=self._status,
                description="Return the current org workspace status. No args.",
            )
        )

    # -- built-in handlers ---------------------------------------------
    def _std(self, **kw: Any) -> dict:
        return {"ok": True, "echo": kw}

    def _workspace(self):
        ws = Path(os.environ.get("EHERMES_WORKSPACE", str(Path.cwd() / "_workspace")))
        ws.mkdir(parents=True, exist_ok=True)
        return ws

    def _plan(self, title: str = "untitled", detail: str = "") -> dict:
        rec = {"title": title, "detail": detail}
        self._write_json("plans.json", rec)
        return {"ok": True, "recorded": rec}

    def _save_note(self, filename: str = "note.md", content: str = "") -> dict:
        fname = filename if filename.endswith((".md", ".txt", ".json")) else filename + ".md"
        path = self._workspace() / fname
        path.write_text(content)
        return {"ok": True, "path": str(path), "bytes": len(content)}

    def _status(self, **_kw: Any) -> dict:
        ws = self._workspace()
        files = sorted(p.name for p in ws.iterdir())
        return {"ok": True, "org_workspace": str(ws), "notes": files}

    def _write_json(self, name, rec):
        ws = self._workspace()
        with (ws / name).open("a") as fh:
            fh.write(json.dumps(rec) + "\n")
        return ws / name

    def _run_tests(self, cmd: str, cwd: str | None = None) -> dict:
        if ";" in cmd or "&&" in cmd or "|" in cmd:
            raise ToolError("compound shell commands are blocked for code.run_tests")
        try:
            res = subprocess.run(
                cmd.split(),
                cwd=cwd or str(Path.cwd()),
                capture_output=True,
                text=True,
                timeout=120,
            )
            return {
                "ok": res.returncode == 0,
                "returncode": res.returncode,
                "stdout_tail": res.stdout[-2000:],
                "stderr_tail": res.stderr[-1000:],
            }
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": str(exc)}

    # -- registry API ---------------------------------------------------
    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool:
        tool = self._tools.get(name)
        if not tool:
            raise ToolError(f"tool not in registry: {name}")
        return tool

    def allowlist(self) -> list[str]:
        return sorted(self._tools)

    def tool_checksum(self) -> str:
        """Stable hash of the registry — used to pin tool versions in audit."""
        payload = "|".join(f"{t.name}:{t.risk}:{t.scope}" for t in sorted(self._tools.values(), key=lambda x: x.name))
        return hashlib.sha256(payload.encode()).hexdigest()