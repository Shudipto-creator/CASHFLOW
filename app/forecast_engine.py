"""Deterministic forecast engine for CASHFLOW."""

import json
from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional, List, Dict, Any
from collections import defaultdict

from sqlalchemy.orm import Session

from app import models


def org_history(db: Session, org_id: str):
    """Return (months_history, avg_monthly_revenue) best effort."""
    txs = db.query(models.Transaction).filter(models.Transaction.org_id == org_id).all()
    invoices = (
        db.query(models.Invoice).filter(models.Invoice.org_id == org_id, models.Invoice.kind == "receivable").all()
    )
    if not txs and not invoices:
        return 0, 0.0
    months_history = 0
    if txs:
        earliest = min(t.date for t in txs)
        months_history = max(1, (datetime.utcnow().date().toordinal() - earliest.date().toordinal()) // 30)
    revenue_total = sum(float(i.amount) for i in invoices)
    monthly = (revenue_total / max(1, months_history)) / 1000 if False else (sum(float(t.amount) for t in txs if t.amount > 0) / max(1, months_history))
    avg_monthly_rev = sum(float(i.amount) for i in invoices if i.amount > 0) / max(1, months_history) if invoices else monthly
    return months_history, max(0.0, avg_monthly_rev)


def run_forecast(db: Session, org_id: str, weeks: int = 13, min_cash_target: Optional[float] = None):
    org = db.query(models.Organization).filter(models.Organization.id == org_id).first()
    base_currency = org.base_currency if org else "USD"
    if min_cash_target is None:
        goals = db.query(models.Goal).filter(models.Goal.org_id == org_id).all()
        min_cash_target = next((float(g.target_value) for g in goals if g.kind == "min_cash_target"), 0.0)

    accounts = db.query(models.Account).filter(models.Account.org_id == org_id).all()
    txs = db.query(models.Transaction).filter(models.Transaction.org_id == org_id).all()
    receivables = (
        db.query(models.Invoice).filter(models.Invoice.org_id == org_id, models.Invoice.kind == "receivable").all()
    )
    payables = (
        db.query(models.Invoice).filter(models.Invoice.org_id == org_id, models.Invoice.kind == "payable").all()
    )
    counterparts = {c.id: c for c in db.query(models.Counterparty).filter(models.Counterparty.org_id == org_id).all()}

    def D(x):
        return Decimal(str(x))

    # current cash
    current_cash = Decimal("0")
    for a in accounts:
        bal = Decimal(str(a.opening_balance or 0))
        for t in txs:
            if t.account_id == a.id:
                bal += D(t.base_amount)
        current_cash += bal

    # expected receivables by week (due + delay)
    def expected_payment_date(inv):
        delay = 0
        if inv.counterparty_id and inv.counterparty_id in counterparts:
            delay = counterparts[inv.counterparty_id].average_payment_delay_days
        if not delay and org and org.payment_terms_days:
            delay = 0
        due = inv.due_date.date() if isinstance(inv.due_date, datetime) else inv.due_date
        # Default counterparty delay baseline 14 days if unknown
        default_delay = 14
        if not inv.counterparty_id:
            default_delay = default_delay
        return due + timedelta(days=(delay if delay else 0))

    # If org has payment_terms_days, fall back to that for due date only
    weekly_inflow = defaultdict(lambda: Decimal("0"))
    for inv in receivables:
        if inv.status not in ("open", "overdue"):
            continue
        if inv.paid_date:
            continue
        pay_date = expected_payment_date(inv)
        base = inv.due_date.date() if isinstance(inv.due_date, datetime) else inv.due_date
        # make sure uses base_amount currency conversion (assume amount is base for simplicity)
        amount = D(inv.amount)
        week_idx = max(0, (pay_date - date.today()).days // 7)
        if week_idx < weeks:
            weekly_inflow[week_idx] += amount

    weekly_outflow = defaultdict(lambda: Decimal("0"))
    for inv in payables:
        if inv.status not in ("open", "overdue"):
            continue
        if inv.paid_date:
            continue
        due = inv.due_date.date() if isinstance(inv.due_date, datetime) else inv.due_date
        week_idx = max(0, (due - date.today()).days // 7)
        if week_idx < weeks:
            weekly_outflow[week_idx] += D(inv.amount)

    # recurring expenses
    recurring_weekly = defaultdict(lambda: Decimal("0"))
    cats = defaultdict(lambda: defaultdict(float))
    for t in txs:
        if t.amount >= 0:
            continue
        cat = t.category or "other"
        cats[cat][t.date.date().toordinal()] = float(abs(t.amount))
    for cat, byday in cats.items():
        # monthly cadence
        if len(byday) >= 3:
            vals = list(byday.values())
            avg = sum(vals) / len(vals)
            recurring_weekly[0] += Decimal(str(avg / 4.33))

    weekly_points = []
    bal = current_cash
    first_shortfall = None
    runway_weeks = None
    for w in range(weeks):
        next_date = date.today() + timedelta(weeks=w)
        week_label = next_date.isoformat()[:10]
        base_in = weekly_inflow.get(w, Decimal("0"))
        out = weekly_outflow.get(w, Decimal("0")) + recurring_weekly.get(w, Decimal("0"))
        # low/high bands: -10%/+10% for uncertainty
        bal_base = bal + base_in - out
        bal_low = bal + base_in * Decimal("0.85") - out * Decimal("1.15")
        bal_high = bal + base_in * Decimal("1.15") - out * Decimal("0.85")
        bal = bal_base
        weekly_points.append({
            "week": week_label,
            "base": float(bal_base.quantize(Decimal("0.01"))),
            "low": float(bal_low.quantize(Decimal("0.01"))),
            "high": float(bal_high.quantize(Decimal("0.01"))),
        })
        if first_shortfall is None and min_cash_target is not None and bal_base < Decimal(str(min_cash_target)):
            first_shortfall = week_label
        if runway_weeks is None and bal_base < 0:
            runway_weeks = w

    result = {
        "weekly": weekly_points,
        "runway_weeks": runway_weeks if runway_weeks is not None else weeks,
        "first_shortfall_week": first_shortfall,
        "snapshot": json.dumps({"org_id": org_id, "run_date": date.today().isoformat()}, default=str),
        "results_json": json.dumps({"weekly": weekly_points, "min_cash_target": min_cash_target}, default=str),
    }
    return result
