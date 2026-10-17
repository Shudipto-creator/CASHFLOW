"""Policy engine: tool tiers, autonomy levels, and authorization (sections 12.2-12.4)."""

from __future__ import annotations

from typing import Optional

from app import models

TOOL_TIERS = {
    "read_transactions": "read",
    "read_invoices": "read",
    "run_forecast": "read",
    "run_risk_scan": "read",
    "compare_financing": "read",
    "search_documents": "read",
    "draft_payment_reminder": "draft",
    "draft_supplier_message": "draft",
    "draft_lender_pack": "draft",
    "send_reminder": "execute",
    "queue_sandbox_payment": "execute",
    "submit_sandbox_application": "execute",
}

TIER_RANK = {"read": 0, "draft": 1, "execute": 2}


def tool_tier(tool: str) -> Optional[str]:
    return TOOL_TIERS.get(tool)


def tier_allowed(autonomy_level: int, tier: str) -> bool:
    rank = {"read": 0, "draft": 1, "execute": 2}[tier]
    return rank <= autonomy_level - 1


def autonomy_max_tier(autonomy_level: int) -> str:
    return ["read", "draft", "execute"][autonomy_level - 1]


def role_allows(autonomy_level: int, tier: str, role: str) -> bool:
    """Role matrix: owner/finance/viewer; execute tools never allowed for viewer."""
    if tier == "execute" and role not in ("owner", "finance"):
        return False
    if tier == "draft" and role == "viewer":
        return False
    return True
