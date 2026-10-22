"""Wilson-style anomaly detection: duplicates, spikes, forgotten subscriptions."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any, Dict, Iterable, List, Optional, Set


def _parse_date(value: str) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.strptime(value[:10], "%Y-%m-%d")
    except ValueError:
        return None


def _merchant_key(description: str) -> str:
    text = (description or "").strip().lower()
    # Collapse whitespace / card suffixes so near-identical merchants match
    for token in ("*", "#", "  "):
        text = text.replace(token, " ")
    return " ".join(text.split())[:80]


def detect_duplicates(
    transactions: Iterable[Dict[str, Any]],
    window_days: int = 3,
    limit: int = 50,
) -> List[Dict[str, Any]]:
    """
    Flag same amount + same description within ``window_days``.

    Mirrors openaccountant/wilson anomaly-detect duplicate self-join.
    """
    rows = sorted(
        (t for t in transactions if t.get("date") and t.get("description") is not None),
        key=lambda t: (t.get("date", ""), t.get("id") or 0),
    )
    findings: List[Dict[str, Any]] = []

    for i, a in enumerate(rows):
        a_date = _parse_date(a["date"])
        if a_date is None:
            continue
        a_amt = round(float(a.get("amount", 0) or 0), 2)
        a_desc = _merchant_key(a.get("description", ""))
        for b in rows[i + 1 :]:
            b_date = _parse_date(b["date"])
            if b_date is None:
                continue
            delta = abs((b_date - a_date).days)
            if delta > window_days:
                # rows are date-sorted; later rows only grow further away once past window
                if b_date > a_date and delta > window_days:
                    break
                continue
            b_amt = round(float(b.get("amount", 0) or 0), 2)
            if a_amt != b_amt:
                continue
            if _merchant_key(b.get("description", "")) != a_desc:
                continue
            findings.append(
                {
                    "type": "duplicate",
                    "severity": "high",
                    "amount": a_amt,
                    "description": a.get("description"),
                    "dates": [a["date"], b["date"]],
                    "transaction_ids": [a.get("id"), b.get("id")],
                    "reason": (
                        f"Same charge of ${abs(a_amt):,.2f} for '{a.get('description')}' "
                        f"appeared twice within {delta} day(s)."
                    ),
                    "potential_savings": abs(a_amt),
                }
            )
            if len(findings) >= limit:
                return findings
    return findings


def detect_spikes(
    transactions: Iterable[Dict[str, Any]],
    multiplier: float = 3.0,
    min_history: int = 3,
    limit: int = 20,
) -> List[Dict[str, Any]]:
    """
    Flag expenses where |amount| > multiplier × merchant average.

    Only considers outflow-like rows (negative amounts, or non-income categories).
    """
    by_merchant: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for txn in transactions:
        amount = float(txn.get("amount", 0) or 0)
        category = (txn.get("category") or "").strip()
        # Prefer signed convention (expenses negative); also treat positive
        # non-income as spend (credit-card style CSVs).
        is_spend = amount < 0 or (
            amount > 0 and category not in {"Income", "Transfer", ""}
        ) or (amount > 0 and category == "")
        if amount == 0:
            continue
        if amount > 0 and category in {"Income", "Transfer"}:
            continue
        if not is_spend and amount > 0 and category == "Income":
            continue
        key = _merchant_key(txn.get("description", ""))
        if not key:
            continue
        by_merchant[key].append(txn)

    findings: List[Dict[str, Any]] = []
    for merchant, rows in by_merchant.items():
        if len(rows) < min_history:
            continue
        magnitudes = [abs(float(r.get("amount", 0) or 0)) for r in rows]
        avg = sum(magnitudes) / len(magnitudes)
        if avg <= 0:
            continue
        for row, mag in zip(rows, magnitudes):
            if mag > multiplier * avg:
                findings.append(
                    {
                        "type": "spike",
                        "severity": "medium" if mag < 5 * avg else "high",
                        "amount": float(row.get("amount", 0) or 0),
                        "description": row.get("description"),
                        "dates": [row.get("date")],
                        "transaction_ids": [row.get("id")],
                        "merchant": merchant,
                        "average_amount": round(avg, 2),
                        "multiplier": round(mag / avg, 2),
                        "reason": (
                            f"Charge of ${mag:,.2f} is {mag / avg:.1f}× the usual "
                            f"${avg:,.2f} average for this merchant."
                        ),
                        "potential_savings": 0.0,
                    }
                )

    findings.sort(key=lambda f: f.get("multiplier", 0), reverse=True)
    return findings[:limit]


def detect_forgotten_subscriptions(
    transactions: Iterable[Dict[str, Any]],
    inactive_days: int = 90,
    limit: int = 20,
) -> List[Dict[str, Any]]:
    """
    Flag recurring / subscription merchants with no recent non-recurring activity.

    Heuristic port of Wilson unused_subscriptions:
    - Treat category == Subscriptions OR is_recurring as subscription charges
    - If last subscription charge is older than ``inactive_days``, or the only
      activity is a repeating charge with no other merchant touch recently,
      surface it as a forgotten / audit candidate.
    """
    rows = list(transactions)
    now = max((_parse_date(t.get("date", "")) for t in rows), default=None)
    if now is None:
        now = datetime.utcnow()

    sub_by_merchant: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    all_by_merchant: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

    for txn in rows:
        key = _merchant_key(txn.get("description", ""))
        if not key:
            continue
        category = (txn.get("category") or "").strip()
        # Never treat income / transfers as forgotten subscriptions
        if category in {"Income", "Transfer"}:
            continue
        all_by_merchant[key].append(txn)
        # Only explicit Subscriptions category (avoids flagging Amazon/payroll)
        if category == "Subscriptions":
            sub_by_merchant[key].append(txn)

    findings: List[Dict[str, Any]] = []
    cutoff = now - timedelta(days=inactive_days)

    for merchant, sub_rows in sub_by_merchant.items():
        dated = [( _parse_date(r.get("date", "")), r) for r in sub_rows]
        dated = [(d, r) for d, r in dated if d is not None]
        if not dated:
            continue
        dated.sort(key=lambda x: x[0])
        last_date, last_row = dated[-1]
        amounts = [abs(float(r.get("amount", 0) or 0)) for _, r in dated]
        typical = sum(amounts) / len(amounts)

        # Forgotten if last charge is old, OR merchant only ever appears as subscription
        # and charge pattern looks stale relative to ledger end date.
        other_activity = [
            _parse_date(r.get("date", ""))
            for r in all_by_merchant[merchant]
            if (r.get("category") or "") != "Subscriptions" and not r.get("is_recurring")
        ]
        other_activity = [d for d in other_activity if d is not None]
        last_other = max(other_activity) if other_activity else None

        stale = last_date <= cutoff
        unused_elsewhere = last_other is not None and last_other <= cutoff

        # Also flag active-looking recurring charges that keep billing with no
        # other merchant interaction for inactive_days (classic "forgotten sub").
        keep_billing_unused = (
            last_date > cutoff
            and (last_other is None or last_other <= cutoff)
            and len(dated) >= 2
        )

        if not (stale or unused_elsewhere or keep_billing_unused):
            continue

        severity = "medium"
        if keep_billing_unused:
            reason = (
                f"Recurring charge (~${typical:,.2f}) for '{last_row.get('description')}' "
                f"is still billing, but there is no other activity with this merchant "
                f"in {inactive_days}+ days — possible forgotten subscription."
            )
            severity = "high"
        elif stale:
            reason = (
                f"Subscription-like charge for '{last_row.get('description')}' last seen "
                f"on {last_date.date().isoformat()} ({(now - last_date).days} days ago)."
            )
        else:
            reason = (
                f"Subscription merchant '{merchant}' has no recent non-subscription activity."
            )

        findings.append(
            {
                "type": "forgotten_subscription",
                "severity": severity,
                "amount": -typical if float(last_row.get("amount", 0) or 0) < 0 else typical,
                "description": last_row.get("description"),
                "dates": [last_date.date().isoformat()],
                "transaction_ids": [last_row.get("id")],
                "merchant": merchant,
                "months_observed": len(dated),
                "reason": reason,
                "potential_savings": round(typical * 12, 2),
                "annual_cost_estimate": round(typical * 12, 2),
            }
        )

    findings.sort(key=lambda f: abs(float(f.get("potential_savings") or 0)), reverse=True)
    return findings[:limit]


def mark_recurring(transactions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Tag transactions that look recurring (same merchant + similar amount ≥ 2 times).
    Mutates copies; does not write to DB.
    """
    by_key: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for txn in transactions:
        key = (
            _merchant_key(txn.get("description", "")),
            round(abs(float(txn.get("amount", 0) or 0)), 2),
        )
        by_key[key].append(txn)

    recurring_ids: Set[Any] = set()
    for (_merchant, _amt), rows in by_key.items():
        if len(rows) >= 2:
            for r in rows:
                if r.get("id") is not None:
                    recurring_ids.add(r["id"])
                r["is_recurring"] = True
        elif (rows[0].get("category") or "") == "Subscriptions":
            rows[0]["is_recurring"] = True
            if rows[0].get("id") is not None:
                recurring_ids.add(rows[0]["id"])

    for txn in transactions:
        if txn.get("id") in recurring_ids:
            txn["is_recurring"] = True
        else:
            txn.setdefault("is_recurring", bool(txn.get("is_recurring")))
    return transactions


def detect_anomalies(
    transactions: List[Dict[str, Any]],
    types: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Run selected anomaly detectors and return a structured report."""
    wanted = set(types or ["all"])
    if "all" in wanted:
        wanted = {"duplicates", "spikes", "forgotten_subscriptions"}

    prepared = mark_recurring([dict(t) for t in transactions])
    report: Dict[str, Any] = {
        "duplicates": [],
        "spikes": [],
        "forgotten_subscriptions": [],
        "summary": {},
    }

    if "duplicates" in wanted:
        report["duplicates"] = detect_duplicates(prepared)
    if "spikes" in wanted:
        report["spikes"] = detect_spikes(prepared)
    if "forgotten_subscriptions" in wanted or "unused_subscriptions" in wanted:
        report["forgotten_subscriptions"] = detect_forgotten_subscriptions(prepared)

    all_findings = (
        report["duplicates"] + report["spikes"] + report["forgotten_subscriptions"]
    )
    savings = sum(float(f.get("potential_savings") or 0) for f in all_findings)
    report["summary"] = {
        "total_flags": len(all_findings),
        "duplicate_count": len(report["duplicates"]),
        "spike_count": len(report["spikes"]),
        "forgotten_subscription_count": len(report["forgotten_subscriptions"]),
        "potential_annual_savings": round(savings, 2),
        "privacy": "local_only",
    }
    return report
