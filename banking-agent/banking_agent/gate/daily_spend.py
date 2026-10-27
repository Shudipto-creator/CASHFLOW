"""The counter the ¥1,000 tier rule reads.

Deliberately independent of okgate's own ``spend_usd`` counter. Two counters
that are expected to agree is defence in depth, not duplication: they are
charged at the same point (a successful ``prepare-transfer``, which is where
okgate prices the call), so if they ever diverge, one of the two layers has
been tampered with or has a bug — and that divergence is itself a signal worth
alerting on.

The day boundary is the *local* date. okgate keys its own day counter the same
way, so the two stay aligned on a single machine.
"""

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from pathlib import Path


class DailySpendLedger:
    """How much the user has authorised today, in CNY."""

    def __init__(self, path: Path, *, today: str | None = None) -> None:
        self._path = path
        self._today = today or date.today().isoformat()

    # -- reads -------------------------------------------------------------

    def spent_today(self) -> Decimal:
        return self._read().get(self._today, Decimal("0"))

    def all_days(self) -> dict[str, Decimal]:
        return self._read()

    # -- writes ------------------------------------------------------------

    def add(self, amount: Decimal) -> Decimal:
        """Commit `amount` to today's total and return the new total."""
        rows = self._read()
        rows[self._today] = rows.get(self._today, Decimal("0")) + Decimal(str(amount))
        self._write(rows)
        return rows[self._today]

    def reset(self) -> None:
        if self._path.exists():
            self._path.unlink()

    # -- storage -----------------------------------------------------------

    def _read(self) -> dict[str, Decimal]:
        if not self._path.exists():
            return {}
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            # A corrupted counter must not silently read as zero: that would
            # let spend through. Fail loudly instead.
            raise RuntimeError(f"daily spend ledger at {self._path} is unreadable")
        return {day: Decimal(str(total)) for day, total in raw.items()}

    def _write(self, rows: dict[str, Decimal]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = {day: str(total) for day, total in sorted(rows.items())}
        self._path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
