"""Multi-factor verification for Red-tier operations.

okgate deliberately has no MFA, so this is where Track 2's "strong
verification — facial recognition, an SMS code, or a USB security token" is
implemented. It runs *before* the tool call reaches the proxy, so a refused
verification means the call never exists.

``SmsCodeMfa`` is a working one-time-code verifier: a 6-digit code, a short
TTL, a bounded number of attempts, and single use. It is transport-agnostic —
the code is handed to a ``deliver`` callback, which in production is your SMS
gateway or push channel and in a demo is a print. It is **not** a real SMS
integration; see the known-risks section of the report.
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable, Optional, Protocol
from uuid import uuid4


class MfaVerifier(Protocol):
    """Anything that can pose a challenge and check the answer."""

    async def challenge(self, *, subject: str, purpose: str) -> str:
        """Start a verification and return its id. Delivers the code out of band."""
        ...

    async def verify(self, *, challenge_id: str, code: str) -> bool:
        """Consume `code` against `challenge_id`. True only once, only if valid."""
        ...


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class _Challenge:
    subject: str
    purpose: str
    code: str
    expires_at: datetime
    attempts_left: int


class SmsCodeMfa:
    """One-time codes with a TTL, an attempt limit, and single use.

    ``deliver`` is the only seam to the outside world: it receives
    ``(subject, challenge_id, code)`` and is responsible for getting the code
    to the human. The default prints it, which is what a demo needs and a
    production deployment must replace.
    """

    def __init__(
        self,
        *,
        deliver: Optional[Callable[[str, str, str], None]] = None,
        ttl: timedelta = timedelta(minutes=2),
        max_attempts: int = 3,
        code_length: int = 6,
        clock: Callable[[], datetime] = _utcnow,
    ) -> None:
        self._deliver = deliver or (
            lambda subject, challenge_id, code: print(
                f"[MFA] code for {subject} ({challenge_id}): {code}"
            )
        )
        self._ttl = ttl
        self._max_attempts = max_attempts
        self._code_length = code_length
        self._now = clock
        self._challenges: dict[str, _Challenge] = {}

    async def challenge(self, *, subject: str, purpose: str) -> str:
        challenge_id = f"mfa_{uuid4().hex[:12]}"
        code = "".join(secrets.choice("0123456789") for _ in range(self._code_length))
        self._challenges[challenge_id] = _Challenge(
            subject=subject,
            purpose=purpose,
            code=code,
            expires_at=self._now() + self._ttl,
            attempts_left=self._max_attempts,
        )
        self._deliver(subject, challenge_id, code)
        return challenge_id

    async def verify(self, *, challenge_id: str, code: str) -> bool:
        challenge = self._challenges.get(challenge_id)
        if challenge is None:
            return False
        if self._now() >= challenge.expires_at:
            # Expired: burn it so a stale code can never be replayed.
            del self._challenges[challenge_id]
            return False

        challenge.attempts_left -= 1
        if challenge.attempts_left <= 0:
            del self._challenges[challenge_id]

        if not secrets.compare_digest(challenge.code, code or ""):
            return False

        # Single use: a verified challenge is consumed.
        del self._challenges[challenge_id]
        return True
