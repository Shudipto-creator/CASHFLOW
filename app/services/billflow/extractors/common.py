"""Shared helpers for deterministic transaction extraction (no LLM)."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

DATE_KEYS = ("date", "transactiondate", "posteddate", "postdate", "transdate", "valuedate")
DESC_KEYS = ("description", "memo", "payee", "narration", "details", "name", "merchant", "item")
AMOUNT_KEYS = ("amount", "transactionamount", "value", "total", "price")
DEBIT_KEYS = ("debit", "withdrawal", "outflow")
CREDIT_KEYS = ("credit", "deposit", "inflow")


def _normalize_header(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (name or "").strip().lower())


def _parse_amount(raw: Any) -> Optional[float]:
    if raw is None:
        return None
    text = str(raw).strip().replace(",", "").replace("$", "").replace("(", "-").replace(")", "")
    if not text or text in {"-", "--"}:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _parse_date(raw: Any) -> Optional[str]:
    if not raw:
        return None
    text = str(raw).strip()
    for fmt in ("%m/%d/%Y", "%Y-%m-%d", "%m-%d-%Y", "%d/%m/%Y", "%Y/%m/%d", "%b %d, %Y", "%d-%b-%Y"):
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def _find_col(headers: List[str], keys: Tuple[str, ...]) -> Optional[int]:
    norm = [_normalize_header(h) for h in headers]
    for i, h in enumerate(norm):
        if h in keys:
            return i
    for i, h in enumerate(norm):
        for k in keys:
            if k in h:
                return i
    return None


def detect_header_row(rows: List[List[Any]]) -> Optional[Tuple[int, Dict[str, int]]]:
    """Return (row_index, colmap) for the first row that has date + (desc or amount)."""
    for i, row in enumerate(rows[:20]):
        if not row or all(c is None or str(c).strip() == "" for c in row):
            continue
        headers = [str(c) if c is not None else "" for c in row]
        date_idx = _find_col(headers, DATE_KEYS)
        desc_idx = _find_col(headers, DESC_KEYS)
        amount_idx = _find_col(headers, AMOUNT_KEYS)
        debit_idx = _find_col(headers, DEBIT_KEYS)
        credit_idx = _find_col(headers, CREDIT_KEYS)
        if date_idx is not None and (desc_idx is not None or amount_idx is not None or debit_idx is not None):
            colmap = {
                "date": date_idx,
                "description": desc_idx,
                "amount": amount_idx,
                "debit": debit_idx,
                "credit": credit_idx,
            }
            return i, colmap
    return None


def rows_to_transactions(rows: List[List[Any]], colmap: Dict[str, int], filename: str, bank: str = "generic") -> Tuple[List[Dict[str, Any]], List[str]]:
    transactions: List[Dict[str, Any]] = []
    errors: List[str] = []
    for row_num, row in enumerate(rows, start=1):
        if not row or all(c is None or str(c).strip() == "" for c in row):
            continue
        date_idx = colmap.get("date")
        desc_idx = colmap.get("description")
        amount_idx = colmap.get("amount")
        if date_idx is None or date_idx >= len(row):
            continue
        date_iso = _parse_date(row[date_idx])
        description = ""
        if desc_idx is not None and desc_idx < len(row) and row[desc_idx] is not None:
            description = str(row[desc_idx]).strip()
        if not date_iso or not description:
            # allow amount-only rows? skip
            if not date_iso:
                continue
            if not description:
                description = "Transaction"
        amount = None
        if amount_idx is not None and amount_idx < len(row):
            amount = _parse_amount(row[amount_idx])
        if amount is None:
            debit_idx = colmap.get("debit")
            credit_idx = colmap.get("credit")
            debit = _parse_amount(row[debit_idx]) if debit_idx is not None and debit_idx < len(row) else None
            credit = _parse_amount(row[credit_idx]) if credit_idx is not None and credit_idx < len(row) else None
            if debit is not None and debit != 0:
                amount = -abs(debit)
            elif credit is not None:
                amount = abs(credit)
        if amount is None:
            errors.append(f"Row {row_num}: could not parse amount")
            continue
        transactions.append({
            "date": date_iso,
            "description": description,
            "amount": round(float(amount), 2),
            "bank": bank,
            "source_file": filename,
            "external_key": f"{date_iso}|{round(float(amount), 2)}|{description.lower()}",
        })
    return transactions, errors[:20]