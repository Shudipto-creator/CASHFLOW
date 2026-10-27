"""Spending summaries by category, merchant, and period."""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple


INFLOW_CATEGORIES = {"Income", "Transfer"}


def _is_outflow(txn: Dict[str, Any]) -> bool:
    amount = float(txn.get("amount", 0) or 0)
    category = (txn.get("category") or "").strip()
    if category in INFLOW_CATEGORIES:
        return False
    if amount < 0:
        return True
    # Credit-card style: purchases often stored as positive
    if amount > 0 and category and category not in INFLOW_CATEGORIES:
        return True
    if amount > 0 and not category:
        return True
    return False


def _is_inflow(txn: Dict[str, Any]) -> bool:
    amount = float(txn.get("amount", 0) or 0)
    category = (txn.get("category") or "").strip()
    if category == "Income":
        return True
    if amount > 0 and category == "Transfer":
        return False
    if amount > 0 and category in INFLOW_CATEGORIES:
        return True
    if amount > 0 and category == "Income":
        return True
    # Explicit positive income-like with no category yet
    return amount > 0 and category == "Income"


def _spend_amount(txn: Dict[str, Any]) -> float:
    return abs(float(txn.get("amount", 0) or 0))


def filter_by_date(
    transactions: List[Dict[str, Any]],
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> List[Dict[str, Any]]:
    out = []
    for txn in transactions:
        d = (txn.get("date") or "")[:10]
        if start_date and d < start_date:
            continue
        if end_date and d > end_date:
            continue
        out.append(txn)
    return out


def spending_by_category(
    transactions: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    totals: Dict[str, float] = defaultdict(float)
    counts: Dict[str, int] = defaultdict(int)
    for txn in transactions:
        if not _is_outflow(txn):
            continue
        cat = (txn.get("category") or "Other").strip() or "Other"
        if cat in INFLOW_CATEGORIES:
            continue
        totals[cat] += _spend_amount(txn)
        counts[cat] += 1

    grand = sum(totals.values()) or 1.0
    rows = [
        {
            "category": cat,
            "total": round(total, 2),
            "count": counts[cat],
            "share_pct": round(100.0 * total / grand, 2),
        }
        for cat, total in totals.items()
    ]
    rows.sort(key=lambda r: r["total"], reverse=True)
    return rows


def spending_by_merchant(
    transactions: List[Dict[str, Any]],
    limit: int = 25,
) -> List[Dict[str, Any]]:
    totals: Dict[str, float] = defaultdict(float)
    counts: Dict[str, int] = defaultdict(int)
    for txn in transactions:
        if not _is_outflow(txn):
            continue
        merchant = (txn.get("description") or "Unknown").strip()
        totals[merchant] += _spend_amount(txn)
        counts[merchant] += 1

    rows = [
        {
            "merchant": merchant,
            "total": round(total, 2),
            "count": counts[merchant],
        }
        for merchant, total in totals.items()
    ]
    rows.sort(key=lambda r: r["total"], reverse=True)
    return rows[:limit]


def monthly_trend(transactions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    spend: Dict[str, float] = defaultdict(float)
    income: Dict[str, float] = defaultdict(float)
    for txn in transactions:
        month = (txn.get("date") or "")[:7]
        if not month:
            continue
        amount = float(txn.get("amount", 0) or 0)
        category = (txn.get("category") or "").strip()
        if category == "Income" or (amount > 0 and category == "Income"):
            income[month] += abs(amount)
        elif _is_outflow(txn):
            spend[month] += _spend_amount(txn)
        elif amount > 0 and category not in {"Transfer"}:
            # Heuristic income
            if category == "Income":
                income[month] += abs(amount)

    months = sorted(set(spend) | set(income))
    return [
        {
            "month": m,
            "spending": round(spend.get(m, 0.0), 2),
            "income": round(income.get(m, 0.0), 2),
            "net": round(income.get(m, 0.0) - spend.get(m, 0.0), 2),
        }
        for m in months
    ]


def build_summary(
    transactions: List[Dict[str, Any]],
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    group_by: str = "category",
) -> Dict[str, Any]:
    """Answer 'Where did my money go?' with structured local math."""
    scoped = filter_by_date(transactions, start_date, end_date)
    outflows = [t for t in scoped if _is_outflow(t)]
    inflows = [
        t
        for t in scoped
        if (t.get("category") or "") == "Income"
        or (
            float(t.get("amount", 0) or 0) > 0
            and (t.get("category") or "") not in {"", "Transfer"}
            and (t.get("category") or "") == "Income"
        )
    ]
    # Broader income: positive + Income category
    income_total = 0.0
    for t in scoped:
        amt = float(t.get("amount", 0) or 0)
        cat = (t.get("category") or "").strip()
        if cat == "Income":
            income_total += abs(amt)
        elif amt > 0 and cat not in {"Transfer"} and cat == "Income":
            income_total += abs(amt)

    spend_total = sum(_spend_amount(t) for t in outflows)
    by_category = spending_by_category(scoped)
    by_merchant = spending_by_merchant(scoped)
    trend = monthly_trend(scoped)

    breakdown = by_category if group_by != "merchant" else by_merchant

    return {
        "question": "Where did my money go?",
        "privacy": "All calculations ran locally in SQLite — no bank data left this machine.",
        "date_range": {
            "start": start_date or (min((t["date"] for t in scoped), default=None)),
            "end": end_date or (max((t["date"] for t in scoped), default=None)),
        },
        "totals": {
            "spending": round(spend_total, 2),
            "income": round(income_total, 2),
            "net": round(income_total - spend_total, 2),
            "transaction_count": len(scoped),
            "outflow_count": len(outflows),
        },
        "by_category": by_category,
        "by_merchant": by_merchant,
        "monthly_trend": trend,
        "breakdown": breakdown,
        "top_category": by_category[0] if by_category else None,
        "answer_text": _narrate(spend_total, income_total, by_category, start_date, end_date),
    }


def _narrate(
    spend_total: float,
    income_total: float,
    by_category: List[Dict[str, Any]],
    start_date: Optional[str],
    end_date: Optional[str],
) -> str:
    period = "the selected period"
    if start_date and end_date:
        period = f"{start_date} → {end_date}"
    elif start_date:
        period = f"since {start_date}"
    elif end_date:
        period = f"through {end_date}"

    if not by_category:
        return f"No categorized spending found for {period}."

    top = by_category[:3]
    parts = ", ".join(f"{c['category']} ${c['total']:,.2f} ({c['share_pct']}%)" for c in top)
    return (
        f"For {period} you spent ${spend_total:,.2f} "
        f"(income recorded ${income_total:,.2f}). "
        f"Top categories: {parts}."
    )


def money_gone_answer(
    transactions: List[Dict[str, Any]],
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> Dict[str, Any]:
    """Convenience wrapper used by Ask CFO / BillFlow ask endpoint."""
    return build_summary(transactions, start_date=start_date, end_date=end_date)
