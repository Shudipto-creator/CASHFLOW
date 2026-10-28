"""Tamper-evident, hash-chained append-only audit ledger.

Independent of okgate's audit.jsonl. Every security decision made by the
backend (signature verification result, schema validation, tier classification,
kill/resume, approval, transfer prepare/execute) is appended here with a
SHA-256 hash chain linking each entry to the previous one.

If any row is edited, verify_chain() returns False, providing tamper evidence
for regulatory compliance.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any


class DecisionLedger:
    """Append-only, hash-chained ledger of security decisions."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._last_hash = self._load_last_hash()

    # -- public API ---------------------------------------------------------

    def append(
        self,
        actor: str,
        action: str,
        payload: dict[str, Any],
        outcome: str,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Append a decision entry and return it (including its hash)."""
        previous_hash = self._last_hash or "0" * 64
        entry: dict[str, Any] = {
            "actor": actor,
            "action": action,
            "payload": payload,
            "outcome": outcome,
            "previous_hash": previous_hash,
            "metadata": metadata or {},
        }
        entry["hash"] = self._hash_entry(entry)
        self._write_entry(entry)
        self._last_hash = entry["hash"]
        return entry

    def verify_chain(self) -> bool:
        """Walk the ledger and verify every hash link. Returns False if any
        entry has been tampered with or is missing."""
        if not self._path.exists():
            return True
        previous_hash = "0" * 64
        with self._path.open("r", encoding="utf-8") as f:
            for line_no, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    return False
                if entry.get("previous_hash") != previous_hash:
                    return False
                expected = self._hash_entry({k: v for k, v in entry.items() if k != "hash"})
                if entry.get("hash") != expected:
                    return False
                previous_hash = entry["hash"]
        return True

    def read_all(self) -> list[dict[str, Any]]:
        """Return all entries, oldest first."""
        if not self._path.exists():
            return []
        entries: list[dict[str, Any]] = []
        with self._path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    entries.append(json.loads(line))
        return entries

    # -- internals ----------------------------------------------------------

    def _hash_entry(self, entry: dict[str, Any]) -> str:
        canonical = json.dumps(entry, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def _load_last_hash(self) -> str | None:
        if not self._path.exists():
            return None
        last: str | None = None
        with self._path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        entry = json.loads(line)
                        last = entry.get("hash")
                    except json.JSONDecodeError:
                        break
        return last

    def _write_entry(self, entry: dict[str, Any]) -> None:
        with self._path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, sort_keys=True) + "\n")


#: Singleton ledger instance (initialized in main.py startup).
decision_ledger: DecisionLedger | None = None


def init_ledger(path: Path) -> DecisionLedger:
    """Initialize the global decision ledger."""
    global decision_ledger
    decision_ledger = DecisionLedger(path)
    return decision_ledger
