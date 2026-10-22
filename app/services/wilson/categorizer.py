"""Rule-based categorizer matching Wilson's 18 spending categories."""

from __future__ import annotations

from typing import Any, Dict, List

from app.services.wilson.categories import CATEGORY_RULES, WILSON_CATEGORIES


def categorize_description(description: str, amount: float = 0.0) -> Dict[str, Any]:
    """
    Categorize a single transaction description.

    Returns category name, confidence (0-1), and whether it matched a rule.
    """
    text = (description or "").lower()

    for keyword, category in CATEGORY_RULES:
        if keyword in text:
            return {
                "category": category,
                "confidence": 0.92,
                "method": "rule",
            }

    # Income heuristic: large positive amounts with deposit-like wording already covered;
    # leftover positives with no rule → Income if clearly a credit, else Other.
    if amount > 0 and any(w in text for w in ("deposit", "credit", "payment from", "ach credit")):
        return {"category": "Income", "confidence": 0.7, "method": "heuristic"}

    if amount > 0 and abs(amount) >= 500 and "transfer" not in text:
        return {"category": "Income", "confidence": 0.55, "method": "heuristic"}

    return {"category": "Other", "confidence": 0.4, "method": "fallback"}


def categorize_transactions(transactions: List[Dict[str, Any]]):
    """Attach category + confidence to each transaction dict. Returns (rows, stats)."""
    categorized = []
    counts: Dict[str, int] = {c: 0 for c in WILSON_CATEGORIES}
    rule_matched = 0
    needing_review = 0

    for txn in transactions:
        result = categorize_description(txn.get("description", ""), float(txn.get("amount", 0) or 0))
        item = {**txn, **result}
        categorized.append(item)
        counts[result["category"]] = counts.get(result["category"], 0) + 1
        if result["method"] == "rule":
            rule_matched += 1
        if result["confidence"] < 0.7:
            needing_review += 1

    return categorized, {
        "total": len(categorized),
        "rule_matched": rule_matched,
        "needing_review": needing_review,
        "categories_applied": {k: v for k, v in counts.items() if v > 0},
    }
