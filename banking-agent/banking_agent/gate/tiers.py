"""Green / Yellow / Red classification — Track 2 §III.1.

This is the part of the security design that **cannot** live in okgate.
okgate's caps are hard blocks with no notion of "and then the user proves who
they are", so strong verification for Red operations has to be decided here,
before the call is allowed to leave for the proxy.

The rule that matters is about the *daily cumulative total*, not the single
amount:

    "Yellow — small transfers with a daily cumulative total of ¥1,000 or less"
    "Red    — large transfers with a daily cumulative total over ¥1,000"

so a ¥600 transfer is Yellow in the morning and Red once ¥600 has already
been authorised today. Classification therefore takes today's committed total
as an input.

Fail closed: anything not explicitly classified is RED, and okgate will
independently refuse it (`classify.unknown: block`) unless it was added to
``classify.read``/``write``/``spend`` in ``okgate.yaml``.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any, Mapping

from .contract import YELLOW_DAILY_CEILING_CNY, Tier, TieredCall

#: Read-only tools: the agent may run these after confirming intent, with no
#: secondary confirmation. Mirrors `classify.read: ["get-*"]` in okgate.yaml.
GREEN_TOOLS = frozenset(
    {
        "get-accounts",
        "get-transactions",
        "get-transaction",
        "get-categories",
        "get-transactions-summary",
        "get-recipients",
    }
)

#: Tools that commit money and carry the amount in their arguments. This is
#: the only place okgate can price a transfer, which is why the spend cap is
#: configured here and not on `execute-transfer`.
TRANSFER_TOOLS = frozenset({"prepare-transfer"})

#: Irreversible, but not priceable from arguments. Mirrors `approval.tools`
#: in okgate.yaml: a human must confirm each one.
CONFIRM_TOOLS = frozenset({"execute-transfer", "create-recipient"})

#: Operations that always require strong verification, whatever the amount.
#: Track 2 lists password changes, lost-card reporting and unblocking, and
#: investment-product subscriptions. bank2ai's standardized surface does not
#: include those tools yet — when a scenario owner adds one, its name goes
#: here *and* into okgate.yaml's classify/approval blocks.
MFA_TOOLS = frozenset()


def to_decimal(value: Any) -> Decimal:
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal("0")


def classify(
    *,
    tool: str,
    args: Mapping[str, Any] | None = None,
    daily_spent_cny: Decimal = Decimal("0"),
) -> TieredCall:
    """Decide the access tier for one prospective tool call."""
    args = args or {}

    if tool in MFA_TOOLS:
        return TieredCall(
            tool=tool,
            tier=Tier.RED,
            reason=f"'{tool}' is a strong-verification operation regardless of amount",
        )

    if tool in GREEN_TOOLS:
        return TieredCall(
            tool=tool,
            tier=Tier.GREEN,
            reason="read-only operation; executed after intent is confirmed, no secondary confirmation",
        )

    if tool in TRANSFER_TOOLS:
        amount = to_decimal(args.get("amount", 0))
        projected = daily_spent_cny + amount
        if projected > YELLOW_DAILY_CEILING_CNY:
            return TieredCall(
                tool=tool,
                tier=Tier.RED,
                reason=(
                    f"daily cumulative would reach ¥{projected:,.2f}, over the "
                    f"¥{YELLOW_DAILY_CEILING_CNY:,.0f} ceiling"
                ),
                amount_cny=amount,
                projected_daily_cny=projected,
            )
        return TieredCall(
            tool=tool,
            tier=Tier.YELLOW,
            reason=(
                f"daily cumulative would reach ¥{projected:,.2f}, within the "
                f"¥{YELLOW_DAILY_CEILING_CNY:,.0f} ceiling"
            ),
            amount_cny=amount,
            projected_daily_cny=projected,
        )

    if tool in CONFIRM_TOOLS:
        return TieredCall(
            tool=tool,
            tier=Tier.YELLOW,
            reason="irreversible operation; the user must confirm the details before execution",
        )

    # Fail closed.
    return TieredCall(
        tool=tool,
        tier=Tier.RED,
        reason=f"'{tool}' is not classified; unknown tools fail closed",
    )
