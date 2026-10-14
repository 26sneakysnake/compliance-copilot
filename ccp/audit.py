"""Append-only, hash-chained audit log.

Each entry stores the SHA-256 of the previous entry, so any edit, deletion or
reordering breaks the chain and is detected by `verify()`. This supports the
record-keeping logic of AI Act Article 12 and the accountability principle of
GDPR Article 5(2). Questions are redacted before being written and users are
pseudonymised.

Tamper-evident, not tamper-proof: someone with write access can rewrite the
whole file. In production the log would go to WORM storage (for example an
immutable Azure Blob container) and the latest hash would be anchored elsewhere.
"""
from __future__ import annotations

import hashlib
import json
import threading
from datetime import datetime, timezone
from pathlib import Path

from . import config
from .redact import pseudonymise, redact

GENESIS = "0" * 64
_lock = threading.Lock()


def _digest(entry: dict) -> str:
    body = {k: v for k, v in entry.items() if k != "hash"}
    return hashlib.sha256(json.dumps(body, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


class AuditLog:
    def __init__(self, path: Path | None = None):
        self.path = Path(path) if path else config.AUDIT_FILE

    def _last_hash(self) -> str:
        if not self.path.exists():
            return GENESIS
        last = None
        with self.path.open("rb") as f:
            for line in f:
                if line.strip():
                    last = line
        return json.loads(last)["hash"] if last else GENESIS

    def record(self, event: str, user: str, role: str, **fields) -> dict:
        with _lock:
            entry = {
                "ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
                "event": event,
                "user": pseudonymise(user),
                "role": role,
                **{k: redact(v) if isinstance(v, str) else v for k, v in fields.items()},
                "prev_hash": self._last_hash(),
            }
            entry["hash"] = _digest(entry)
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
            return entry

    def entries(self, limit: int | None = None) -> list[dict]:
        if not self.path.exists():
            return []
        rows = [json.loads(line) for line in self.path.read_text(encoding="utf-8").splitlines() if line.strip()]
        return rows[-limit:] if limit else rows

    def verify(self) -> tuple[bool, int | None]:
        """Return (ok, index of the first broken entry)."""
        prev = GENESIS
        for i, entry in enumerate(self.entries()):
            if entry.get("prev_hash") != prev or _digest(entry) != entry.get("hash"):
                return False, i
            prev = entry["hash"]
        return True, None
