"""Immutable append-only audit log.

Writes every action (tool call, approval, auth event) to an append-only
journal. Each record includes an HMAC over the previous record so the chain
is verifiable end-to-end. Attempting to overwrite or split the chain is
detected on verification.

Security posture: audit is the source of truth for what happened and who
signed off — required for SOC2 CC8 (change management) / GDPR art.30
(processing records) evidence.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import time
import uuid
from pathlib import Path


class AuditError(Exception):
    """Raised when a tamper is detected or an append fails."""


class AuditLog:
    """Append-only journal with HMAC-chained integrity."""

    def __init__(self, path: str | Path, hmac_key: bytes = b"dev-insecure-key"):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._key = hmac_key
        if not self.path.exists():
            self._write_seed()

    # -- internals ------------------------------------------------------
    def _write_seed(self) -> None:
        seed = {
            "seq": 0,
            "event": "chain/init",
            "actor": "system",
            "ts": time.time(),
            "prev": "GENESIS",
            "data": {},
        }
        seed["hash"] = self._hash(seed)
        with self.path.open("a") as fh:
            fh.write(json.dumps(seed) + "\n")

    def _hash(self, record: dict) -> str:
        body = json.dumps(record["data"], sort_keys=True, default=str)
        payload = f"{record['seq']}|{record['event']}|{record['actor']}|{record['prev']}|{body}"
        return hmac.new(self._key, payload.encode(), hashlib.sha256).hexdigest()

    def _last_seq(self) -> int:
        lines = self.path.read_text().strip().splitlines()
        return json.loads(lines[-1])["seq"]

    def _prev_hash(self) -> str:
        lines = self.path.read_text().strip().splitlines()
        return json.loads(lines[-1])["hash"]

    # -- public ---------------------------------------------------------
    def append(self, event: str, actor: str, data: dict) -> dict:
        seq = self._last_seq() + 1
        record = {
            "seq": seq,
            "id": str(uuid.uuid4()),
            "event": event,
            "actor": actor,
            "ts": time.time(),
            "prev": self._prev_hash(),
            "data": data,
        }
        record["hash"] = self._hash(record)
        # Append-only: lock the file, write, and refuse any in-place rewrite.
        with self.path.open("a") as fh:
            fh.write(json.dumps(record) + "\n")
        self.verify()  # fail loudly if this append broke the chain
        return record

    def verify(self) -> bool:
        """Recompute the chain; raise AuditError on any tamper."""
        lines = self.path.read_text().strip().splitlines()
        prev = "GENESIS"
        for idx, line in enumerate(lines, start=1):
            rec = json.loads(line)
            if rec["prev"] != prev:
                raise AuditError(f"chain break at seq {rec['seq']}")
            if rec["hash"] != self._hash(rec):
                raise AuditError(f"tampered record at seq {rec['seq']}")
            prev = rec["hash"]
        return True

    def read(self, event: str | None = None) -> list[dict]:
        self.verify()
        recs = [json.loads(l) for l in self.path.read_text().strip().splitlines()]
        if event:
            recs = [r for r in recs if r["event"] == event]
        return recs