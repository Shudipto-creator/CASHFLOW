"""The Green/Yellow/Red rule, in isolation.

The boundary that matters is the *projected* daily total, because Track 2
keys the tier off the cumulative total rather than the single instruction.
"""

from decimal import Decimal

import pytest

from banking_agent.gate import Tier, classify
from banking_agent.gate.contract import YELLOW_DAILY_CEILING_CNY


def test_reads_are_green():
    decision = classify(tool="get-accounts")
    assert decision.tier is Tier.GREEN
    assert decision.needs_confirmation is False
    assert decision.needs_mfa is False


def test_a_transfer_within_the_ceiling_is_yellow():
    decision = classify(tool="prepare-transfer", args={"amount": 300})
    assert decision.tier is Tier.YELLOW
    assert decision.needs_confirmation is True
    assert decision.needs_mfa is False
    assert decision.amount_cny == Decimal("300")
    assert decision.projected_daily_cny == Decimal("300")


def test_exactly_the_ceiling_is_still_yellow():
    """"¥1,000 or less" — the ceiling itself is Yellow, not Red."""
    decision = classify(
        tool="prepare-transfer",
        args={"amount": YELLOW_DAILY_CEILING_CNY},
    )
    assert decision.tier is Tier.YELLOW


@pytest.mark.parametrize("amount", ["1000.01", "1001", "50000"])
def test_above_the_ceiling_is_red(amount):
    decision = classify(tool="prepare-transfer", args={"amount": amount})
    assert decision.tier is Tier.RED
    assert decision.needs_mfa is True


def test_yesterdays_spend_does_not_count():
    decision = classify(tool="prepare-transfer", args={"amount": 900}, daily_spent_cny=Decimal("0"))
    assert decision.tier is Tier.YELLOW


def test_a_small_amount_becomes_red_once_today_is_high_enough():
    """The rule is about the cumulative total: ¥600 + ¥500 > ¥1,000."""
    first = classify(tool="prepare-transfer", args={"amount": 600}, daily_spent_cny=Decimal("0"))
    second = classify(tool="prepare-transfer", args={"amount": 500}, daily_spent_cny=Decimal("600"))
    assert first.tier is Tier.YELLOW
    assert second.tier is Tier.RED
    assert second.projected_daily_cny == Decimal("1100")


def test_landing_exactly_on_the_ceiling_after_spend_is_yellow():
    decision = classify(tool="prepare-transfer", args={"amount": 400}, daily_spent_cny=Decimal("600"))
    assert decision.tier is Tier.YELLOW


def test_irreversible_operations_need_confirmation():
    decision = classify(tool="execute-transfer")
    assert decision.tier is Tier.YELLOW
    assert decision.needs_confirmation is True


def test_unknown_tools_fail_closed():
    decision = classify(tool="delete-everything")
    assert decision.tier is Tier.RED


def test_an_unparseable_amount_does_not_bypass_the_rule():
    """Fail closed: a junk amount is treated as zero, so it lands in Yellow
    and still needs a human — okgate independently rejects it via its schema."""
    decision = classify(tool="prepare-transfer", args={"amount": "not-a-number"})
    assert decision.tier is Tier.YELLOW
    assert decision.amount_cny == Decimal("0")
