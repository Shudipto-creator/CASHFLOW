"""Strong verification for the Red tier.

okgate has no MFA, so this is the layer that carries Track 2's "facial
recognition, SMS code, or USB token". It has to behave like a one-time code:
short-lived, single-use, and dead after too many wrong guesses.
"""

from datetime import datetime, timedelta, timezone
from pathlib import Path
import re
import sys
from types import SimpleNamespace

from banking_agent.gate import SmsCodeMfa

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from app.services.llm_banking_agent import BankingExecutor


class Clock:
    """A hand-cranked clock, so expiry is tested without sleeping."""

    def __init__(self) -> None:
        self.now = datetime(2026, 10, 21, 9, 0, tzinfo=timezone.utc)

    def __call__(self) -> datetime:
        return self.now

    def advance(self, **kwargs) -> None:
        self.now += timedelta(**kwargs)


def make_mfa(**kwargs):
    delivered: dict[str, str] = {}
    kwargs.setdefault("deliver", lambda s, cid, code: delivered.__setitem__(cid, code))
    return SmsCodeMfa(**kwargs), delivered


async def test_a_challenge_delivers_six_digits():
    mfa, delivered = make_mfa()
    challenge_id = await mfa.challenge(subject="张小伟", purpose="transfer")

    assert challenge_id.startswith("mfa_")
    assert len(delivered[challenge_id]) == 6
    assert delivered[challenge_id].isdigit()


async def test_the_right_code_verifies_once():
    mfa, delivered = make_mfa()
    challenge_id = await mfa.challenge(subject="张小伟", purpose="transfer")
    code = delivered[challenge_id]

    assert await mfa.verify(challenge_id=challenge_id, code=code) is True
    assert await mfa.verify(challenge_id=challenge_id, code=code) is False


async def test_a_wrong_code_does_not_verify():
    mfa, _ = make_mfa()
    challenge_id = await mfa.challenge(subject="张小伟", purpose="transfer")
    assert await mfa.verify(challenge_id=challenge_id, code="000000") is False


async def test_an_unknown_challenge_never_verifies():
    mfa, _ = make_mfa()
    assert await mfa.verify(challenge_id="mfa_missing", code="123456") is False


async def test_too_many_wrong_guesses_burn_the_challenge():
    mfa, delivered = make_mfa(max_attempts=3)
    challenge_id = await mfa.challenge(subject="张小伟", purpose="transfer")

    for _ in range(3):
        assert await mfa.verify(challenge_id=challenge_id, code="000000") is False
    # The real code is useless once the attempt budget is gone.
    assert await mfa.verify(challenge_id=challenge_id, code=delivered[challenge_id]) is False


async def test_an_expired_code_is_refused():
    clock = Clock()
    mfa, delivered = make_mfa(ttl=timedelta(minutes=2), clock=clock)
    challenge_id = await mfa.challenge(subject="张小伟", purpose="transfer")

    clock.advance(minutes=3)
    assert await mfa.verify(challenge_id=challenge_id, code=delivered[challenge_id]) is False


async def test_a_code_is_still_good_just_before_it_expires():
    clock = Clock()
    mfa, delivered = make_mfa(ttl=timedelta(minutes=2), clock=clock)
    challenge_id = await mfa.challenge(subject="张小伟", purpose="transfer")

    clock.advance(seconds=119)
    assert await mfa.verify(challenge_id=challenge_id, code=delivered[challenge_id]) is True


async def test_executor_keeps_mfa_challenge_across_requests(tmp_path, capsys):
    executor = BankingExecutor(
        policy=Path("policy.yaml"),
        root=Path("."),
        state_dir=tmp_path,
    )
    first_request_verifier = executor._mfa_verifier()
    challenge_id = await first_request_verifier.challenge(
        subject="test-user", purpose="transfer"
    )
    code = re.search(
        r"verification code (\d{6})", capsys.readouterr().out
    ).group(1)

    next_request_verifier = executor._mfa_verifier()
    assert next_request_verifier is first_request_verifier
    assert await next_request_verifier.verify(challenge_id=challenge_id, code=code)


def test_transfer_response_does_not_expose_mfa_code():
    outcome = SimpleNamespace(
        ok=False,
        stage="mfa",
        prepared=SimpleNamespace(code="MFA_REQUIRED", details={"challenge_id": "mfa_test"}),
        executed=None,
        tier=None,
        intent_id=None,
        approval_id=None,
        approval_command=None,
        message="Verification required.",
        needs_confirmation=False,
        needs_mfa=True,
        needs_approval=False,
        details={},
    )

    payload = BankingExecutor._transfer_payload(outcome)

    assert payload["mfa_challenge_id"] == "mfa_test"
    assert "mfa_codes" not in payload
