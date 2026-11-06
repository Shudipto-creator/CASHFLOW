"""Short-lived one-time codes for local-demo password recovery."""

from __future__ import annotations

import secrets
import time
from dataclasses import dataclass
from datetime import timedelta
from hmac import compare_digest
from uuid import uuid4


@dataclass
class _RecoveryChallenge:
    email: str
    code: str
    expires_at: float
    attempts_left: int


class PasswordRecoveryCodes:
    def __init__(
        self,
        *,
        ttl: timedelta = timedelta(minutes=5),
        cooldown: timedelta = timedelta(seconds=60),
        max_attempts: int = 3,
    ) -> None:
        self._ttl_seconds = ttl.total_seconds()
        self._cooldown_seconds = cooldown.total_seconds()
        self._max_attempts = max_attempts
        self._challenges: dict[str, _RecoveryChallenge] = {}
        self._last_request: dict[str, float] = {}

    def issue(self, email: str) -> str:
        email = email.strip().casefold()
        now = time.monotonic()
        self._challenges = {
            challenge_id: challenge
            for challenge_id, challenge in self._challenges.items()
            if challenge.expires_at > now
        }
        self._last_request = {
            requested_email: requested_at
            for requested_email, requested_at in self._last_request.items()
            if now - requested_at < self._cooldown_seconds
        }
        last_request = self._last_request.get(email)
        if last_request is not None and now - last_request < self._cooldown_seconds:
            raise RecoveryCooldownError("Please wait before requesting another recovery code.")

        self._last_request[email] = now
        challenge_id = f"recovery_{uuid4().hex}"
        code = f"{secrets.randbelow(1_000_000):06d}"
        self._challenges[challenge_id] = _RecoveryChallenge(
            email=email,
            code=code,
            expires_at=now + self._ttl_seconds,
            attempts_left=self._max_attempts,
        )
        print(
            f"[FINN DEMO PASSWORD RECOVERY] Code for {email} "
            f"(challenge {challenge_id}): {code}",
            flush=True,
        )
        return challenge_id

    def verify(self, email: str, challenge_id: str, code: str) -> bool:
        challenge = self._challenges.get(challenge_id)
        if challenge is None:
            return False
        if time.monotonic() >= challenge.expires_at:
            del self._challenges[challenge_id]
            return False

        challenge.attempts_left -= 1
        if challenge.attempts_left <= 0:
            del self._challenges[challenge_id]

        valid = (
            challenge.email == email.strip().casefold()
            and compare_digest(challenge.code, code or "")
        )
        if not valid:
            return False

        self._challenges.pop(challenge_id, None)
        return True


class RecoveryCooldownError(Exception):
    """Raised when a new recovery code is requested before the cooldown ends."""
