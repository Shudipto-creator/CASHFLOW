"""The orchestrator, against a stub for the proxy.

These tests deliberately replace `GateClient` with a stub. The point is to
prove what the gate decides *before* anything reaches okgate: a Yellow call
that was not confirmed must never appear in the stub's call log. The live
integration is covered by `python -m banking_agent.demo.run`; here we pin the
refusal logic, which is easier to get wrong and impossible to see from outside.
"""

import hashlib
from decimal import Decimal

import pytest

from banking_agent.gate import (
    DailySpendLedger,
    GateCode,
    GateResult,
    SecureBankGate,
    SmsCodeMfa,
    Tier,
)

DEBTOR = "acc_cmb_001"
CREDITOR = {
    "name": "李娜",
    "accountIdentifier": {
        "type": "accountNumber",
        "accountNumber": "6225 8888 0000 1234",
        "country": "CN",
    },
}


class FakeClient:
    """Stands in for the okgate proxy: records calls, replays canned results."""

    def __init__(self, results=None):
        self.calls: list[tuple[str, dict]] = []
        self._queued = list(results or [])

    async def call(self, tool, args=None):
        call_args = dict(args or {})
        self.calls.append((tool, call_args))
        if self._queued:
            return self._queued.pop(0)
        return self._default(tool, call_args)

    @staticmethod
    def _default(tool, args):
        if tool == "prepare-transfer":
            # The bank issues a stable intent per distinct call: retrying the
            # same arguments replays the same intent (which the gate must
            # count once), while a different amount gets a fresh one.
            digest = hashlib.sha256(repr(sorted(args.items())).encode("utf-8")).hexdigest()[:12]
            return GateResult(
                tool=tool,
                ok=True,
                message="A transfer has been prepared.",
                value={"item": {"transferIntentId": f"intent_{digest}"}},
            )
        return GateResult(tool=tool, ok=True, value={"items": []})

    def tools_called(self) -> list[str]:
        return [tool for tool, _ in self.calls]


@pytest.fixture
def stack(tmp_path):
    delivered: dict[str, str] = {}

    def deliver(subject, challenge_id, code):
        delivered[challenge_id] = code

    client = FakeClient()
    gate = SecureBankGate(
        client=client,
        spend=DailySpendLedger(tmp_path / "spend.json"),
        mfa=SmsCodeMfa(deliver=deliver),
        subject="张小伟",
    )
    return gate, client, delivered


async def spend_today(gate, amount, **extra):
    return await gate.transfer(
        debtor_account_id=DEBTOR, creditor=CREDITOR, amount=amount, confirmed=True, **extra
    )


def first_challenge(outcome) -> str:
    return (outcome.prepared.details or {}).get("challenge_id")


# --- Green ----------------------------------------------------------------


async def test_a_read_reaches_the_proxy_unchallenged(stack):
    gate, client, _ = stack
    outcome = await gate.call("get-accounts")

    assert outcome.ok is True
    assert outcome.tier is Tier.GREEN
    assert client.tools_called() == ["get-accounts"]


# --- Yellow ---------------------------------------------------------------


async def test_an_unconfirmed_transfer_never_reaches_the_proxy(stack):
    gate, client, _ = stack
    outcome = await gate.transfer(debtor_account_id=DEBTOR, creditor=CREDITOR, amount=600)

    assert outcome.prepared.code == GateCode.CONFIRMATION_REQUIRED.value
    assert outcome.tier is Tier.YELLOW
    assert client.calls == []
    assert gate.spent_today() == Decimal("0")


async def test_a_confirmed_transfer_is_sent_and_counted(stack):
    gate, client, _ = stack
    outcome = await spend_today(gate, 600)

    assert outcome.ok is True
    assert outcome.intent_id is not None and outcome.intent_id.startswith("intent_")
    assert client.tools_called() == ["prepare-transfer"]
    assert gate.spent_today() == Decimal("600")


async def test_the_held_message_tells_the_ui_what_to_confirm(stack):
    gate, _, _ = stack
    outcome = await gate.transfer(debtor_account_id=DEBTOR, creditor=CREDITOR, amount=250)

    assert "¥250.00" in outcome.message
    assert outcome.prepared.details["spent_today_cny"] == "0"


# --- Red ------------------------------------------------------------------


async def test_a_red_transfer_asks_for_verification_first(stack):
    gate, client, delivered = stack
    await spend_today(gate, 600)
    calls_before = len(client.calls)

    outcome = await gate.transfer(debtor_account_id=DEBTOR, creditor=CREDITOR, amount=500)

    assert outcome.tier is Tier.RED
    assert outcome.prepared.code == GateCode.MFA_REQUIRED.value
    assert len(client.calls) == calls_before, "the proxy must not see an unverified call"
    assert delivered[first_challenge(outcome)].isdigit()


async def test_a_wrong_code_is_refused(stack):
    gate, client, _ = stack
    await spend_today(gate, 600)
    first = await gate.transfer(debtor_account_id=DEBTOR, creditor=CREDITOR, amount=500)
    calls_before = len(client.calls)

    outcome = await spend_today(
        gate, 500, mfa_challenge_id=first_challenge(first), mfa_code="000000"
    )

    assert outcome.prepared.code == GateCode.MFA_FAILED.value
    assert len(client.calls) == calls_before


async def test_the_right_code_releases_a_red_transfer(stack):
    gate, client, delivered = stack
    await spend_today(gate, 600)
    first = await gate.transfer(debtor_account_id=DEBTOR, creditor=CREDITOR, amount=500)
    challenge = first_challenge(first)

    outcome = await spend_today(
        gate, 500, mfa_challenge_id=challenge, mfa_code=delivered[challenge]
    )

    assert outcome.ok is True
    assert gate.spent_today() == Decimal("1100")


async def test_a_verified_code_cannot_be_replayed(stack):
    gate, _, delivered = stack
    await spend_today(gate, 600)
    first = await gate.transfer(debtor_account_id=DEBTOR, creditor=CREDITOR, amount=500)
    challenge = first_challenge(first)

    await spend_today(gate, 500, mfa_challenge_id=challenge, mfa_code=delivered[challenge])
    replay = await spend_today(
        gate, 500, mfa_challenge_id=challenge, mfa_code=delivered[challenge]
    )

    assert replay.prepared.code == GateCode.MFA_FAILED.value


async def test_a_red_call_without_a_challenge_id_is_refused(stack):
    gate, client, _ = stack
    await spend_today(gate, 600)

    outcome = await spend_today(gate, 500, mfa_code="123456")

    assert outcome.prepared.code == GateCode.MFA_FAILED.value
    assert client.tools_called() == ["prepare-transfer"]


async def test_red_fails_closed_when_no_verifier_is_wired(tmp_path):
    """A missing MFA verifier must refuse the call, never skip the check."""
    client = FakeClient()
    gate = SecureBankGate(
        client=client, spend=DailySpendLedger(tmp_path / "spend.json"), mfa=None
    )

    outcome = await gate.transfer(debtor_account_id=DEBTOR, creditor=CREDITOR, amount=5000)

    assert outcome.prepared.code == GateCode.MFA_REQUIRED.value
    assert outcome.prepared.details["challenge_id"] is None
    assert client.calls == []


# --- okgate passes through ------------------------------------------------


async def test_a_proxy_refusal_is_passed_through_untouched(stack):
    gate, client, _ = stack
    client._queued.append(
        GateResult(
            tool="prepare-transfer",
            ok=False,
            code=GateCode.KILLED.value,
            message="okgate kill switch is on",
        )
    )

    outcome = await spend_today(gate, 100)

    assert outcome.prepared.code == GateCode.KILLED.value
    assert outcome.prepared.result.refused_by_gate is True
    assert gate.spent_today() == Decimal("0"), "a refused call must not be charged"


async def test_the_approval_details_are_surfaced_for_the_ui(stack):
    gate, client, _ = stack
    client._queued.append(
        GateResult(
            tool="execute-transfer",
            ok=False,
            code=GateCode.APPROVAL_REQUIRED.value,
            message='"execute-transfer" needs a human\'s approval before it runs (approval apr_9c6cc79efe)',
            details={
                "approvalId": "apr_9c6cc79efe",
                "command": "okgate approve apr_9c6cc79efe",
            },
        )
    )

    outcome = await gate.execute("intent_fixed")

    assert outcome.needs_approval is True
    assert outcome.approval_id == "apr_9c6cc79efe"
    assert outcome.approval_command == "okgate approve apr_9c6cc79efe"


async def test_the_approval_id_is_recovered_from_the_message_when_details_are_missing(stack):
    gate, client, _ = stack
    client._queued.append(
        GateResult(
            tool="execute-transfer",
            ok=False,
            code=GateCode.APPROVAL_REQUIRED.value,
            message='"execute-transfer" needs a human\'s approval (approval apr_abc123)',
        )
    )

    outcome = await gate.execute("intent_fixed")

    assert outcome.approval_id == "apr_abc123"


# --- counting -------------------------------------------------------------


async def test_a_retried_prepare_is_counted_once(stack):
    """The bank replays the same intent for a retry; the day total must not grow."""
    gate, _, _ = stack
    await spend_today(gate, 100)
    await spend_today(gate, 100)

    assert gate.spent_today() == Decimal("100")


async def test_the_response_payload_is_reachable_from_the_outcome(stack):
    gate, _, _ = stack
    outcome = await gate.call("get-accounts")
    assert outcome.value == {"items": []}


async def test_the_tier_can_be_previewed_without_calling(stack):
    gate, client, _ = stack
    preview = gate.tier_for("prepare-transfer", {"amount": 2000})

    assert preview.tier is Tier.RED
    assert client.calls == []
