"""FINN SQLite banking backend, scoped to the authenticated application user.

This service is deliberately server-only.  A browser never supplies a FINN
customer id: the durable app-user-to-customer link is resolved here.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError

from app.database import SessionLocal
from app.models import BankCustomerLink, User

DB_PATH = Path(__file__).resolve().parents[2] / "data" / "finndb.sqlite"
INTENT_TTL = timedelta(minutes=5)


def _connect() -> sqlite3.Connection:
    if not DB_PATH.exists():
        raise HTTPException(status_code=503, detail="FINN banking database is unavailable")
    con = sqlite3.connect(DB_PATH, timeout=10, isolation_level=None)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    con.execute("""CREATE TABLE IF NOT EXISTS finn_transfer_intents (
        intent_id TEXT PRIMARY KEY, customer_id TEXT NOT NULL, debtor_account_id TEXT NOT NULL,
        creditor_name TEXT NOT NULL, creditor_account_number TEXT NOT NULL,
        amount NUMERIC NOT NULL, currency_code TEXT NOT NULL, description TEXT,
        created_at TEXT NOT NULL, expires_at TEXT NOT NULL, executed_at TEXT
    )""")
    intent_columns = {row[1] for row in con.execute("PRAGMA table_info(finn_transfer_intents)")}
    if "creditor_customer_id" not in intent_columns:
        con.execute("ALTER TABLE finn_transfer_intents ADD COLUMN creditor_customer_id TEXT")
    if "require_internal" not in intent_columns:
        con.execute("ALTER TABLE finn_transfer_intents ADD COLUMN require_internal INTEGER NOT NULL DEFAULT 0")
    return con


def customer_id_for(user: User) -> str:
    """Return one exclusive FINN customer for this app user, allocating once."""
    session = SessionLocal()
    try:
        with _connect() as con:
            all_ids = [r[0] for r in con.execute("SELECT customer_id FROM customers ORDER BY customer_id")]
            matching_ids = [r[0] for r in con.execute(
                "SELECT customer_id FROM customers WHERE legal_name = ? COLLATE NOCASE ORDER BY customer_id",
                (user.company_name.strip(),),
            )]
        candidates = matching_ids + [customer_id for customer_id in all_ids if customer_id not in matching_ids]
        for _ in range(len(candidates) + 1):
            link = session.query(BankCustomerLink).filter_by(user_id=user.user_id).first()
            if link:
                return link.customer_id
            assigned = {row[0] for row in session.query(BankCustomerLink.customer_id).all()}
            customer_id = next((candidate for candidate in candidates if candidate not in assigned), None)
            if customer_id is None:
                raise HTTPException(status_code=409, detail="No unassigned FINN customer is available")
            session.add(BankCustomerLink(user_id=user.user_id, customer_id=customer_id))
            try:
                session.commit()
                return customer_id
            except IntegrityError:
                session.rollback()
        raise HTTPException(status_code=409, detail="Could not allocate a unique FINN customer for this user")
    except HTTPException:
        session.rollback()
        raise
    finally:
        session.close()


def transfer_account_for_customer(customer_id: str) -> dict:
    """Resolve an eligible CNY account for a FINNDB customer."""
    with _connect() as con:
        customer = con.execute(
            "SELECT legal_name, customer_status, kyc_status FROM customers WHERE customer_id = ?",
            (customer_id,),
        ).fetchone()
        if customer is None or customer["customer_status"] != "ACTIVE" or customer["kyc_status"] != "VERIFIED":
            raise HTTPException(status_code=409, detail="This FINNDB customer is not eligible for transfers.")
        row = con.execute(
            """SELECT a.account_id, a.account_number, a.product_name, a.account_type,
                      a.currency_code, a.available_balance
               FROM accounts a
               JOIN account_holders h ON h.account_id = a.account_id
               WHERE h.customer_id = ?
                 AND h.holder_role IN ('PRIMARY', 'JOINT')
                 AND a.account_status = 'ACTIVE'
                 AND a.currency_code = 'CNY'
                 AND a.account_type IN ('CURRENT', 'SAVINGS')
               ORDER BY CASE h.holder_role WHEN 'PRIMARY' THEN 0 ELSE 1 END,
                        CASE a.account_type WHEN 'CURRENT' THEN 0 ELSE 1 END,
                        a.opened_at, a.account_id
               LIMIT 1""",
            (customer_id,),
        ).fetchone()
    if row is None:
        raise HTTPException(status_code=409, detail="No eligible FINNDB transfer account is available for this user.")
    return {
        "id": row["account_id"],
        "account_number": row["account_number"],
        "name": row["product_name"],
        "currency": row["currency_code"],
        "available_balance": float(row["available_balance"]),
        "customer_id": customer_id,
    }


def transfer_account_for(user: User) -> dict:
    """Resolve an eligible CNY account without exposing it to clients."""
    return transfer_account_for_customer(customer_id_for(user))


def search_transfer_customers(name: str, *, exclude_customer_id: str | None = None, limit: int = 20) -> list[dict]:
    """Search active, verified FINNDB customers with an eligible destination account."""
    search_term = name.strip()
    if len(search_term) < 2:
        return []
    escaped = search_term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    pattern = f"%{escaped}%"
    with _connect() as con:
        rows = con.execute(
            """SELECT c.customer_id, c.legal_name
               FROM customers c
               WHERE c.customer_status = 'ACTIVE'
                 AND c.kyc_status = 'VERIFIED'
                 AND c.customer_id != COALESCE(?, '')
                 AND c.legal_name LIKE ? ESCAPE '\\' COLLATE NOCASE
                 AND EXISTS (
                     SELECT 1
                     FROM account_holders h
                     JOIN accounts a ON a.account_id = h.account_id
                     WHERE h.customer_id = c.customer_id
                       AND h.holder_role IN ('PRIMARY', 'JOINT')
                       AND a.account_status = 'ACTIVE'
                       AND a.currency_code = 'CNY'
                       AND a.account_type IN ('CURRENT', 'SAVINGS')
                 )
               ORDER BY c.legal_name COLLATE NOCASE, c.customer_id
               LIMIT ?""",
            (exclude_customer_id, pattern, max(1, min(int(limit), 50))),
        ).fetchall()
    return [{"customer_id": row["customer_id"], "name": row["legal_name"]} for row in rows]


def transfer_customer(customer_id: str) -> dict:
    """Return a verified customer display name after validating transfer eligibility."""
    with _connect() as con:
        row = con.execute(
            "SELECT customer_id, legal_name FROM customers WHERE customer_id = ?",
            (customer_id,),
        ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="FINNDB customer was not found.")
    transfer_account_for_customer(customer_id)
    return {"customer_id": row["customer_id"], "name": row["legal_name"]}


def _owned_account(con: sqlite3.Connection, customer_id: str, account_id: str) -> sqlite3.Row:
    row = con.execute("""SELECT a.* FROM accounts a JOIN account_holders h ON h.account_id=a.account_id
        WHERE h.customer_id=? AND a.account_id=? AND h.holder_role IN ('PRIMARY','JOINT')""", (customer_id, account_id)).fetchone()
    if row is None:
        raise HTTPException(status_code=403, detail="This account is not available to the signed-in customer")
    return row


def accounts_for(user: User) -> dict:
    customer_id = customer_id_for(user)
    with _connect() as con:
        rows = con.execute("""SELECT DISTINCT a.* FROM accounts a JOIN account_holders h ON h.account_id=a.account_id
            WHERE h.customer_id=? ORDER BY a.opened_at, a.account_id""", (customer_id,)).fetchall()
    return {"items": [{"id": r["account_id"], "accountNumber": r["account_number"], "name": r["product_name"],
                       "accountType": r["account_type"], "currency": r["currency_code"], "balance": float(r["ledger_balance"]),
                       "availableBalance": float(r["available_balance"]), "status": "Enabled" if r["account_status"] == "ACTIVE" else "Blocked"}
                      for r in rows]}


def transactions_for(user: User, count: int | None = 10) -> dict:
    customer_id = customer_id_for(user)
    with _connect() as con:
        rows = con.execute("""SELECT t.* FROM account_transactions t JOIN account_holders h ON h.account_id=t.account_id
            WHERE h.customer_id=? ORDER BY t.booked_at DESC LIMIT ?""", (customer_id, max(1, min(int(count or 10), 500)))).fetchall()
    return {"items": [{"id": r["transaction_id"], "accountId": r["account_id"],
                       "amount": float(r["amount"]) * (-1 if r["direction"] == "DEBIT" else 1),
                       "date": r["booked_at"][:10], "description": r["description"] or r["transaction_type"],
                       "categoryId": r["merchant_category"] or r["transaction_type"], "currency": r["currency_code"]}
                      for r in rows]}


def transaction_totals_for(
    user: User,
    direction: str,
    start_date: str | None = None,
    end_date: str | None = None,
) -> dict:
    if direction not in {"CREDIT", "DEBIT"}:
        raise ValueError("Transaction direction must be CREDIT or DEBIT")

    customer_id = customer_id_for(user)
    conditions = [
        "t.direction = ?",
        "t.transaction_status = 'POSTED'",
        "EXISTS (SELECT 1 FROM account_holders h WHERE h.account_id = t.account_id AND h.customer_id = ?)",
    ]
    params: list[str] = [direction, customer_id]
    if start_date:
        conditions.append("t.value_date >= ?")
        params.append(start_date)
    if end_date:
        conditions.append("t.value_date <= ?")
        params.append(end_date)

    with _connect() as con:
        rows = con.execute(
            f"""SELECT t.currency_code, COUNT(*) AS transaction_count, SUM(t.amount) AS total
                FROM account_transactions t
                WHERE {' AND '.join(conditions)}
                GROUP BY t.currency_code
                ORDER BY t.currency_code""",
            params,
        ).fetchall()

    return {
        "items": [
            {
                "currency": row["currency_code"],
                "transaction_count": int(row["transaction_count"]),
                "total": float(row["total"] or 0),
            }
            for row in rows
        ]
    }


def prepare_transfer(user: User, *, debtor_account_id: str, creditor_name: str, creditor_account_number: str,
                     amount: float, currency: str, description: str | None,
                     creditor_customer_id: str | None = None, require_internal: bool = False) -> str:
    customer_id = customer_id_for(user)
    if currency != "CNY":
        raise HTTPException(status_code=422, detail="FINN transfers currently support CNY only")
    now = datetime.now(timezone.utc)
    with _connect() as con:
        con.execute("BEGIN IMMEDIATE")
        account = _owned_account(con, customer_id, debtor_account_id)
        if account["account_status"] != "ACTIVE" or account["currency_code"] != currency:
            raise HTTPException(status_code=409, detail="Source account cannot make this transfer")
        if float(account["available_balance"]) < amount:
            raise HTTPException(status_code=409, detail="Insufficient available balance")
        intent_id = f"finn_{uuid4().hex}"
        con.execute(
            """INSERT INTO finn_transfer_intents (
                   intent_id, customer_id, debtor_account_id, creditor_name,
                   creditor_account_number, amount, currency_code, description,
                   created_at, expires_at, executed_at, creditor_customer_id, require_internal
               ) VALUES (?,?,?,?,?,?,?,?,?,?,NULL,?,?)""",
            (
                intent_id, customer_id, debtor_account_id, creditor_name,
                creditor_account_number.replace(' ', ''), amount, currency, description,
                now.isoformat(), (now + INTENT_TTL).isoformat(), creditor_customer_id,
                int(require_internal),
            ),
        )
        con.commit()
    return intent_id


def execute_transfer(user: User, intent_id: str) -> dict:
    customer_id = customer_id_for(user)
    now = datetime.now(timezone.utc)
    with _connect() as con:
        con.execute("BEGIN IMMEDIATE")
        intent = con.execute("SELECT * FROM finn_transfer_intents WHERE intent_id=?", (intent_id,)).fetchone()
        if intent is None or intent["customer_id"] != customer_id:
            raise HTTPException(status_code=404, detail="Transfer intent was not found for this user")
        if intent["executed_at"]:
            raise HTTPException(status_code=409, detail="Transfer intent has already been executed")
        if datetime.fromisoformat(intent["expires_at"]) <= now:
            raise HTTPException(status_code=409, detail="Transfer intent has expired")
        source = _owned_account(con, customer_id, intent["debtor_account_id"])
        amount = float(intent["amount"])
        if source["account_status"] != "ACTIVE" or float(source["available_balance"]) < amount:
            raise HTTPException(status_code=409, detail="Source account no longer has sufficient available balance")
        number = intent["creditor_account_number"]
        destination = con.execute("SELECT * FROM accounts WHERE account_number=? AND currency_code='CNY' AND account_status='ACTIVE'", (number,)).fetchone()
        if intent["require_internal"]:
            if destination is None or destination["account_id"] == source["account_id"]:
                raise HTTPException(status_code=409, detail="The linked recipient account is no longer available")
            recipient_holding = con.execute(
                """SELECT 1 FROM account_holders
                   WHERE account_id = ? AND customer_id = ?
                     AND holder_role IN ('PRIMARY', 'JOINT')""",
                (destination["account_id"], intent["creditor_customer_id"]),
            ).fetchone()
            if recipient_holding is None:
                raise HTTPException(status_code=409, detail="The linked recipient no longer owns this FINNDB account")
        transfer_id, debit_id = f"TRF-{uuid4().hex[:16]}", f"TXN-{uuid4().hex[:16]}"
        beneficiary_id = None
        if destination is None:
            beneficiary_id = f"BEN-{uuid4().hex[:16]}"
            con.execute("INSERT INTO beneficiaries VALUES (?,?,?,?,NULL,?,'EXTERNAL','CNY','EXTERNAL','VERIFIED',?)",
                        (beneficiary_id, customer_id, intent["creditor_name"], intent["creditor_name"], f"****{number[-4:]}", now.isoformat()))
        con.execute("INSERT INTO transfers VALUES (?,?,?,?,?,?, 'CNY',1,?,?,?,?,?)",
                    (transfer_id, f"FINN-{uuid4().hex}", source["account_id"], destination["account_id"] if destination else None,
                     beneficiary_id, amount, 'INTERNAL' if destination else 'EXTERNAL', 'COMPLETED', intent["description"], now.isoformat(), now.isoformat()))
        source_after = float(source["ledger_balance"]) - amount
        con.execute("UPDATE accounts SET available_balance=?, ledger_balance=? WHERE account_id=?", (source_after, source_after, source["account_id"]))
        con.execute("INSERT INTO account_transactions VALUES (?,?,?,?,?,?, 'CNY', ?, 'POSTED', ?, NULL, ?, ?, ?)",
                    (debit_id, source["account_id"], transfer_id, 'TRANSFER_OUT','DEBIT', amount, source_after,
                     intent["creditor_name"], intent["description"] or f"Transfer to {intent['creditor_name']}", now.isoformat(), now.date().isoformat()))
        if destination:
            dest_after = float(destination["ledger_balance"]) + amount
            con.execute("UPDATE accounts SET available_balance=?, ledger_balance=? WHERE account_id=?", (dest_after, dest_after, destination["account_id"]))
            con.execute("INSERT INTO account_transactions VALUES (?,?,?,?,?,?, 'CNY', ?, 'POSTED', ?, NULL, ?, ?, ?)",
                        (f"TXN-{uuid4().hex[:16]}", destination["account_id"], transfer_id, 'TRANSFER_IN','CREDIT', amount, dest_after,
                         source["product_name"], intent["description"] or f"Transfer from {source['account_id']}", now.isoformat(), now.date().isoformat()))
        con.execute("UPDATE finn_transfer_intents SET executed_at=? WHERE intent_id=?", (now.isoformat(), intent_id))
        con.execute("INSERT INTO audit_logs VALUES (?,?,?,?,?,?,?, ?, ?)",
                    (f"AUD-{uuid4().hex[:16]}", customer_id, None, transfer_id, 'TRANSFER_EXECUTED', 'CUSTOMER', 'SUCCESS', now.isoformat(), f"FINN transfer executed by app user {user.user_id}"))
        con.commit()
    return {"transfer_id": transfer_id, "transaction_id": debit_id, "amount": amount, "currency": "CNY"}
