"""The local daily spend counter the tier rule reads."""

from decimal import Decimal

import pytest

from banking_agent.gate import DailySpendLedger


def test_a_fresh_ledger_is_empty(tmp_path):
    assert DailySpendLedger(tmp_path / "spend.json").spent_today() == Decimal("0")


def test_add_returns_the_running_total(tmp_path):
    ledger = DailySpendLedger(tmp_path / "spend.json")
    assert ledger.add(Decimal("600")) == Decimal("600")
    assert ledger.add(Decimal("500")) == Decimal("1100")
    assert ledger.spent_today() == Decimal("1100")


def test_the_total_survives_a_new_process(tmp_path):
    path = tmp_path / "spend.json"
    DailySpendLedger(path).add(Decimal("250"))
    assert DailySpendLedger(path).spent_today() == Decimal("250")


def test_days_are_counted_separately(tmp_path):
    path = tmp_path / "spend.json"
    yesterday = DailySpendLedger(path, today="2026-10-20")
    today = DailySpendLedger(path, today="2026-10-21")
    yesterday.add(Decimal("1000"))
    today.add(Decimal("10"))
    assert today.spent_today() == Decimal("10")
    assert yesterday.spent_today() == Decimal("1000")
    assert today.all_days() == {"2026-10-20": Decimal("1000"), "2026-10-21": Decimal("10")}


def test_reset_clears_every_day(tmp_path):
    ledger = DailySpendLedger(tmp_path / "spend.json")
    ledger.add(Decimal("700"))
    ledger.reset()
    assert ledger.spent_today() == Decimal("0")


def test_an_unreadable_ledger_raises_rather_than_reading_zero(tmp_path):
    """Reading a corrupted counter as ¥0 would silently let spend through."""
    path = tmp_path / "spend.json"
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(RuntimeError):
        DailySpendLedger(path).spent_today()
