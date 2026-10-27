"""The orchestrator: tier rules + MFA + okgate + the daily counter.

One primitive, :meth:`SecureBankGate.call`, is the only way a tool call is
allowed to leave this process. It runs the layers in a fixed order and stops
at the first one that refuses:

    1. classify        — Green / Yellow / Red (``tiers.py``)
    2. MFA             — Red only, because okgate has no MFA (``mfa.py``)
    3. confirmation    — Yellow only
    4. GateClient.call — okgate's kill switch, scope, approvals, loop
                         breaker, caps and audit chain (``client.py``)
    5. charge          — the local daily total the Yellow/Red rule reads

Layers 1-3 and 5 exist because okgate cannot express them; layer 4 is okgate's
and is never bypassed. The refusal vocabulary is shared (``contract.py``) so a
caller renders every outcome with one shape.

The protocol is deliberately *interactive*: a Red call does not fail, it
returns ``MFA_REQUIRED`` carrying a challenge id, and the caller retries with
the code. That is what makes the same entry point usable by both the CLI demo
and an HTTP endpoint.

Two phases of a transfer
------------------------
bank2ai splits a transfer into ``prepare-transfer`` (prices it, reserves an
intent) and ``execute-transfer`` (moves the money, takes only the intent id).
The tier rule and okgate's spend cap both attach to the first phase, since
that is the only call that carries an amount. :meth:`SecureBankGate.transfer`
and :meth:`SecureBankGate.execute` wrap the two phases and return a
:class:`TransferOutcome` the UI can render directly.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Mapping, Optional

from .client import GateClient
from .contract import GateCode, GateOutcome, GateResult, Tier
from .daily_spend import DailySpendLedger
from .mfa import MfaVerifier
from .tiers import TRANSFER_TOOLS, classify, to_decimal

#: okgate embeds the approval id in the cause text, e.g.
#: `"execute-transfer" needs a human's approval before it runs (approval apr_9c6cc79efe)`.
_APPROVAL_RE = re.compile(r"\bapr_[0-9a-fA-F]+\b")


def _approval_id(text: str) -> Optional[str]:
    match = _APPROVAL_RE.search(text or "")
    return match.group(0) if match else None


def _intent_id(value: Optional[Mapping[str, Any]]) -> Optional[str]:
    """Pull ``transferIntentId`` out of a prepare-transfer response."""
    if not isinstance(value, Mapping):
        return None
    item = value.get("item")
    if not isinstance(item, Mapping):
        return None
    intent = item.get("transferIntentId")
    return intent if isinstance(intent, str) else None


@dataclass
class TransferOutcome:
    """A transfer attempt as the UI sees it.

    Holds the gate outcome of whichever phase ran, so the frontend can render
    "awaiting confirmation", "awaiting approval", or "settled" from one object.
    """

    ok: bool
    stage: str
    """``prepared`` | ``executed`` | ``refused``."""

    tier: Optional[Tier] = None
    intent_id: Optional[str] = None
    approval_id: Optional[str] = None
    approval_command: Optional[str] = None
    message: str = ""
    prepared: Optional[GateOutcome] = None
    executed: Optional[GateOutcome] = None

    @property
    def needs_confirmation(self) -> bool:
        return bool(self.prepared and self.prepared.code == GateCode.CONFIRMATION_REQUIRED.value)

    @property
    def needs_mfa(self) -> bool:
        return bool(self.prepared and self.prepared.code == GateCode.MFA_REQUIRED.value)

    @property
    def needs_approval(self) -> bool:
        return bool(self.executed and self.executed.code == GateCode.APPROVAL_REQUIRED.value)


class SecureBankGate:
    """The only route from the agent to the bank."""

    def __init__(
        self,
        *,
        client: GateClient,
        spend: DailySpendLedger,
        mfa: Optional[MfaVerifier] = None,
        subject: str = "account-holder",
    ) -> None:
        self.client = client
        self.spend = spend
        self.mfa = mfa
        self.subject = subject
        #: Intents already counted against today's total. A retried
        #: prepare-transfer returns the same intent id from the bank's
        #: idempotency cache; counting it twice would wrongly promote a
        #: Yellow operation to Red on the next call.
        self._charged_intents: set[str] = set()

    # -- the primitive -----------------------------------------------------

    async def call(
        self,
        tool: str,
        args: Optional[Mapping[str, Any]] = None,
        *,
        confirmed: bool = False,
        mfa_challenge_id: Optional[str] = None,
        mfa_code: Optional[str] = None,
    ) -> GateOutcome:
        """Classify, verify, then call `tool` through the gate.

        `confirmed` answers a Yellow confirmation prompt. `mfa_code` (with the
        `mfa_challenge_id` from a previous ``MFA_REQUIRED``) answers a Red
        challenge. A refusal returns a :class:`GateOutcome`; it never raises.
        """
        call_args = dict(args or {})
        spent_before = self.spend.spent_today()
        decision = classify(tool=tool, args=call_args, daily_spent_cny=spent_before)
        tiering: dict[str, Any] = {
            "tier": decision.tier,
            "amount_cny": decision.amount_cny,
            "projected_daily_cny": decision.projected_daily_cny,
        }

        # --- Red: strong verification, before anything leaves for the proxy.
        if decision.needs_mfa:
            if mfa_code is None:
                challenge_id = await self._challenge(decision.reason)
                return GateOutcome(
                    ok=False,
                    code=GateCode.MFA_REQUIRED.value,
                    message=f"{decision.reason}; strong verification is required first",
                    details={
                        "challenge_id": challenge_id,
                        "reason": decision.reason,
                        "spent_today_cny": str(spent_before),
                    },
                    **tiering,
                )
            if not await self._verify(mfa_challenge_id, mfa_code):
                return GateOutcome(
                    ok=False,
                    code=GateCode.MFA_FAILED.value,
                    message="strong verification failed; the call was not sent",
                    **tiering,
                )

        # --- Yellow: the user confirms the details first.
        elif decision.needs_confirmation and not confirmed:
            return GateOutcome(
                ok=False,
                code=GateCode.CONFIRMATION_REQUIRED.value,
                message=f"{decision.reason}; confirm the details with the user first",
                details={"reason": decision.reason, "spent_today_cny": str(spent_before)},
                **tiering,
            )

        # --- okgate: kill switch, scope, approvals, loop breaker, caps, audit.
        result = await self.client.call(tool, call_args)
        outcome = GateOutcome.from_result(result, **tiering)
        self._annotate(outcome, result, tool, call_args)
        return outcome

    # -- two-phase transfer ------------------------------------------------

    async def transfer(
        self,
        *,
        debtor_account_id: str,
        creditor: Mapping[str, Any],
        amount: Any,
        currency: str = "CNY",
        rail: str = "swift",
        description: Optional[str] = None,
        confirmed: bool = False,
        mfa_challenge_id: Optional[str] = None,
        mfa_code: Optional[str] = None,
    ) -> TransferOutcome:
        """Prepare a transfer, enforcing the tier rule on the amount."""
        args: dict[str, Any] = {
            "debtor_account_id": debtor_account_id,
            "creditor": dict(creditor),
            "amount": amount,
            "currency": currency,
            "rail": rail,
        }
        if description:
            args["description"] = description

        outcome = await self.call(
            "prepare-transfer",
            args,
            confirmed=confirmed,
            mfa_challenge_id=mfa_challenge_id,
            mfa_code=mfa_code,
        )
        return TransferOutcome(
            ok=outcome.ok,
            stage="prepared" if outcome.ok else "refused",
            tier=outcome.tier,
            intent_id=outcome.transfer_intent_id,
            message=outcome.message,
            prepared=outcome,
        )

    async def execute(self, intent_id: str) -> TransferOutcome:
        """Settle a prepared intent.

        Passes ``confirmed=True`` on purpose: the human gate on this phase is
        okgate's own approval (``APPROVAL_REQUIRED``), not a second local
        prompt. The money moves only once a human has run ``okgate approve``.
        """
        outcome = await self.call(
            "execute-transfer",
            {"transfer_intent_id": intent_id},
            confirmed=True,
        )
        return TransferOutcome(
            ok=outcome.ok,
            stage="executed" if outcome.ok else "refused",
            tier=outcome.tier,
            intent_id=intent_id,
            approval_id=outcome.approval_id,
            approval_command=outcome.approval_command,
            message=outcome.message,
            executed=outcome,
        )

    # -- internals ---------------------------------------------------------

    async def _challenge(self, reason: str) -> Optional[str]:
        if self.mfa is None:
            # No verifier wired: still refuse rather than let a Red call
            # through unverified. The caller sees MFA_REQUIRED with no id and
            # must fix the wiring.
            return None
        return await self.mfa.challenge(subject=self.subject, purpose=reason)

    async def _verify(self, challenge_id: Optional[str], code: str) -> bool:
        if self.mfa is None or not challenge_id:
            return False
        return await self.mfa.verify(challenge_id=challenge_id, code=code)

    def _annotate(
        self,
        outcome: GateOutcome,
        result: GateResult,
        tool: str,
        args: Mapping[str, Any],
    ) -> None:
        """Attach the ids the UI needs and charge what was just authorised."""
        if result.code == GateCode.APPROVAL_REQUIRED.value:
            details = result.details or {}
            found = details.get("approvalId") or _approval_id(result.message)
            if found:
                outcome.approval_id = found
                outcome.approval_command = details.get("command") or GateClient.approval_hint(found)

        if not result.ok:
            return

        if tool in TRANSFER_TOOLS:
            intent = _intent_id(result.value)
            outcome.transfer_intent_id = intent
            self._charge(intent, args)

    def _charge(self, intent_id: Optional[str], args: Mapping[str, Any]) -> None:
        """Commit a settled prepare to today's total, once per intent."""
        if intent_id is None or intent_id in self._charged_intents:
            return
        amount = to_decimal(args.get("amount", 0))
        if amount <= 0:
            return
        # The mock bank's accounts are all CNY, so a non-CNY amount never
        # reaches here (the bank refuses it as `currency_mismatch` first) and
        # the 1:1 CNY mapping documented in okgate.yaml holds.
        self._charged_intents.add(intent_id)
        self.spend.add(amount)

    # -- state the UI reads ------------------------------------------------

    def spent_today(self) -> Decimal:
        return self.spend.spent_today()

    def tier_for(self, tool: str, args: Optional[Mapping[str, Any]] = None) -> Any:
        """Preview the tier of a prospective call without making it."""
        return classify(tool=tool, args=args or {}, daily_spent_cny=self.spend.spent_today())
