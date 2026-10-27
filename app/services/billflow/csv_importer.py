"""Bank CSV import with Chase / Amex / Bank of America / generic detection."""

from __future__ import annotations

import csv
import hashlib
import io
import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple


def _normalize_header(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (name or "").strip().lower())


def _parse_amount(raw: str) -> Optional[float]:
    if raw is None:
        return None
    text = str(raw).strip().replace(",", "").replace("$", "").replace("(", "-").replace(")", "")
    if not text or text in {"-", "--"}:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _parse_date(raw: str) -> Optional[str]:
    if not raw:
        return None
    text = str(raw).strip()
    for fmt in ("%m/%d/%Y", "%Y-%m-%d", "%m-%d-%Y", "%d/%m/%Y", "%Y/%m/%d", "%b %d, %Y"):
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            continue
    # Excel-ish serial fallback not needed for bank CSVs
    return None


def detect_bank(headers: List[str]) -> str:
    normalized = [_normalize_header(h) for h in headers]
    joined = "|".join(normalized)

    if "transactiondate" in normalized and "postdate" in normalized and "description" in normalized:
        return "chase"
    if "cardmember" in normalized or ("reference" in normalized and "date" in normalized and "amount" in normalized):
        return "amex"
    if "runningbal" in joined or "runningbalance" in joined:
        return "bank_of_america"
    return "generic"


def _map_columns(headers: List[str], bank: str) -> Dict[str, int]:
    idx = {_normalize_header(h): i for i, h in enumerate(headers)}

    def find(*names: str) -> Optional[int]:
        for name in names:
            if name in idx:
                return idx[name]
        return None

    if bank == "chase":
        return {
            "date": find("transactiondate", "date"),
            "description": find("description"),
            "amount": find("amount"),
            "type": find("type"),
        }
    if bank == "amex":
        return {
            "date": find("date"),
            "description": find("description"),
            "amount": find("amount"),
        }
    if bank == "bank_of_america":
        return {
            "date": find("date"),
            "description": find("description"),
            "amount": find("amount"),
        }
    return {
        "date": find("date", "transactiondate", "posteddate", "postdate", "transdate"),
        "description": find("description", "memo", "payee", "narration", "details", "name"),
        "amount": find("amount", "transactionamount", "debit", "value"),
        "credit": find("credit"),
        "debit": find("debit"),
    }


def file_hash(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def parse_bank_csv(content: bytes, filename: str = "") -> Dict[str, Any]:
    """
    Parse a bank CSV into normalized transaction dicts.

    Returns:
        {
          bank, filename, file_hash, transactions: [{date, description, amount, raw}],
          preview: first 5, errors: [...]
        }
    """
    text = content.decode("utf-8-sig", errors="replace")
    # Skip common preamble rows until a header-looking line appears
    sample = text[:4096]
    dialect = csv.Sniffer().sniff(sample, delimiters=",;\t") if sample.strip() else csv.excel
    reader = csv.reader(io.StringIO(text), dialect)

    rows = list(reader)
    if not rows:
        return {
            "bank": "unknown",
            "filename": filename,
            "file_hash": file_hash(content),
            "transactions": [],
            "preview": [],
            "errors": ["Empty CSV file"],
        }

    header_idx = 0
    for i, row in enumerate(rows[:15]):
        joined = " ".join(row).lower()
        if any(k in joined for k in ("date", "description", "amount", "post date")):
            header_idx = i
            break

    headers = rows[header_idx]
    bank = detect_bank(headers)
    colmap = _map_columns(headers, bank)
    errors: List[str] = []
    transactions: List[Dict[str, Any]] = []

    for row_num, row in enumerate(rows[header_idx + 1 :], start=header_idx + 2):
        if not row or all(not str(c).strip() for c in row):
            continue

        date_idx = colmap.get("date")
        desc_idx = colmap.get("description")
        amount_idx = colmap.get("amount")

        if date_idx is None or desc_idx is None:
            errors.append(f"Row {row_num}: missing date/description columns")
            continue

        if date_idx >= len(row) or desc_idx >= len(row):
            continue

        date_iso = _parse_date(row[date_idx])
        description = str(row[desc_idx]).strip()
        if not date_iso or not description:
            continue

        amount = None
        if amount_idx is not None and amount_idx < len(row):
            amount = _parse_amount(row[amount_idx])

        # Generic debit/credit split
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

        # Chase credit-card convention: expenses often positive — keep sign as provided.
        # For generic bank accounts, outflows are usually negative already.
        transactions.append(
            {
                "date": date_iso,
                "description": description,
                "amount": round(float(amount), 2),
                "bank": bank,
                "source_file": filename,
                "external_key": f"{date_iso}|{round(float(amount), 2)}|{description.lower()}",
            }
        )

    return {
        "bank": bank,
        "filename": filename,
        "file_hash": file_hash(content),
        "transactions": transactions,
        "preview": transactions[:5],
        "errors": errors[:20],
        "date_range_start": min((t["date"] for t in transactions), default=None),
        "date_range_end": max((t["date"] for t in transactions), default=None),
    }


def deduplicate_transactions(
    candidates: List[Dict[str, Any]],
    existing_keys: set,
) -> Tuple[List[Dict[str, Any]], int]:
    """Drop transactions already present (date + amount + description)."""
    fresh = []
    duplicates = 0
    seen = set(existing_keys)
    for txn in candidates:
        key = txn.get("external_key") or f"{txn['date']}|{txn['amount']}|{txn['description'].lower()}"
        if key in seen:
            duplicates += 1
            continue
        seen.add(key)
        fresh.append(txn)
    return fresh, duplicates
