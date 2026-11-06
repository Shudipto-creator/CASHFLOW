"""Create the standalone FINN banking demonstration database.

The database deliberately models a general retail bank and is not coupled to
the application's current tables or business rules.
"""

from __future__ import annotations

import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path


DB_PATH = Path(__file__).resolve().parents[1] / "data" / "finndb.sqlite"


SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE customers (
    customer_id TEXT PRIMARY KEY,
    customer_number TEXT NOT NULL UNIQUE,
    legal_name TEXT NOT NULL,
    date_of_birth TEXT NOT NULL,
    national_id_masked TEXT NOT NULL,
    residency_country TEXT NOT NULL DEFAULT 'CN',
    tax_residency_country TEXT NOT NULL DEFAULT 'CN',
    kyc_status TEXT NOT NULL DEFAULT 'VERIFIED'
        CHECK (kyc_status IN ('PENDING','VERIFIED','REJECTED','EXPIRED')),
    customer_status TEXT NOT NULL DEFAULT 'ACTIVE'
        CHECK (customer_status IN ('ACTIVE','SUSPENDED','CLOSED','DECEASED')),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE customer_addresses (
    address_id TEXT PRIMARY KEY,
    customer_id TEXT NOT NULL REFERENCES customers(customer_id),
    address_type TEXT NOT NULL CHECK (address_type IN ('HOME','WORK','MAILING')),
    line1 TEXT NOT NULL, city TEXT NOT NULL, province TEXT NOT NULL,
    postal_code TEXT, country_code TEXT NOT NULL DEFAULT 'CN',
    is_primary INTEGER NOT NULL DEFAULT 0 CHECK (is_primary IN (0,1))
);
CREATE UNIQUE INDEX uq_primary_address ON customer_addresses(customer_id) WHERE is_primary = 1;

CREATE TABLE customer_contacts (
    contact_id TEXT PRIMARY KEY,
    customer_id TEXT NOT NULL REFERENCES customers(customer_id),
    contact_type TEXT NOT NULL CHECK (contact_type IN ('MOBILE','EMAIL')),
    contact_value TEXT NOT NULL,
    is_verified INTEGER NOT NULL DEFAULT 0 CHECK (is_verified IN (0,1)),
    is_primary INTEGER NOT NULL DEFAULT 0 CHECK (is_primary IN (0,1)),
    UNIQUE(customer_id, contact_type, contact_value)
);
CREATE UNIQUE INDEX uq_primary_contact_type ON customer_contacts(customer_id, contact_type) WHERE is_primary = 1;

CREATE TABLE accounts (
    account_id TEXT PRIMARY KEY,
    account_number TEXT NOT NULL UNIQUE,
    account_type TEXT NOT NULL CHECK (account_type IN ('CURRENT','SAVINGS','FIXED_DEPOSIT','CREDIT')),
    product_name TEXT NOT NULL,
    currency_code TEXT NOT NULL DEFAULT 'CNY' CHECK (length(currency_code) = 3),
    account_status TEXT NOT NULL DEFAULT 'ACTIVE'
        CHECK (account_status IN ('PENDING','ACTIVE','FROZEN','DORMANT','CLOSED')),
    opened_at TEXT NOT NULL, closed_at TEXT,
    overdraft_limit NUMERIC NOT NULL DEFAULT 0 CHECK (overdraft_limit >= 0),
    available_balance NUMERIC NOT NULL DEFAULT 0,
    ledger_balance NUMERIC NOT NULL DEFAULT 0,
    CHECK (closed_at IS NULL OR account_status = 'CLOSED')
);

CREATE TABLE account_holders (
    account_id TEXT NOT NULL REFERENCES accounts(account_id),
    customer_id TEXT NOT NULL REFERENCES customers(customer_id),
    holder_role TEXT NOT NULL CHECK (holder_role IN ('PRIMARY','JOINT','AUTHORIZED')),
    ownership_percent NUMERIC NOT NULL DEFAULT 100 CHECK (ownership_percent >= 0 AND ownership_percent <= 100),
    added_at TEXT NOT NULL,
    PRIMARY KEY (account_id, customer_id)
);

CREATE TABLE account_holds (
    hold_id TEXT PRIMARY KEY,
    account_id TEXT NOT NULL REFERENCES accounts(account_id),
    hold_type TEXT NOT NULL CHECK (hold_type IN ('LEGAL','FRAUD','COMPLIANCE','AMOUNT')),
    amount NUMERIC NOT NULL DEFAULT 0 CHECK (amount >= 0),
    reason TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'ACTIVE'
        CHECK (status IN ('ACTIVE','RELEASED','EXPIRED')),
    placed_at TEXT NOT NULL, released_at TEXT
);

CREATE TABLE beneficiaries (
    beneficiary_id TEXT PRIMARY KEY,
    customer_id TEXT NOT NULL REFERENCES customers(customer_id),
    display_name TEXT NOT NULL, bank_name TEXT,
    account_name TEXT NOT NULL, account_number_masked TEXT NOT NULL,
    bank_routing_code TEXT, currency_code TEXT NOT NULL DEFAULT 'CNY',
    beneficiary_type TEXT NOT NULL CHECK (beneficiary_type IN ('INTERNAL','EXTERNAL')),
    verification_status TEXT NOT NULL DEFAULT 'VERIFIED'
        CHECK (verification_status IN ('PENDING','VERIFIED','BLOCKED')),
    created_at TEXT NOT NULL
);

CREATE TABLE cards (
    card_id TEXT PRIMARY KEY,
    account_id TEXT NOT NULL REFERENCES accounts(account_id),
    cardholder_customer_id TEXT NOT NULL REFERENCES customers(customer_id),
    card_token TEXT NOT NULL UNIQUE,
    last_four TEXT NOT NULL CHECK (length(last_four) = 4),
    card_type TEXT NOT NULL CHECK (card_type IN ('DEBIT','CREDIT','PREPAID')),
    form_factor TEXT NOT NULL CHECK (form_factor IN ('PHYSICAL','VIRTUAL')),
    card_status TEXT NOT NULL DEFAULT 'ACTIVE'
        CHECK (card_status IN ('PENDING','ACTIVE','FROZEN','LOST','STOLEN','EXPIRED','CANCELLED')),
    issued_at TEXT NOT NULL, expires_on TEXT NOT NULL, activated_at TEXT,
    daily_purchase_limit NUMERIC NOT NULL DEFAULT 50000 CHECK (daily_purchase_limit >= 0),
    daily_cash_limit NUMERIC NOT NULL DEFAULT 5000 CHECK (daily_cash_limit >= 0)
);

CREATE TABLE card_events (
    card_event_id TEXT PRIMARY KEY,
    card_id TEXT NOT NULL REFERENCES cards(card_id),
    event_type TEXT NOT NULL CHECK (event_type IN ('ISSUED','ACTIVATED','FROZEN','UNFROZEN','LOST_REPORTED','REPLACED','LIMIT_CHANGED')),
    event_at TEXT NOT NULL, initiated_by TEXT NOT NULL, notes TEXT
);

CREATE TABLE transfers (
    transfer_id TEXT PRIMARY KEY,
    client_reference TEXT NOT NULL UNIQUE,
    source_account_id TEXT NOT NULL REFERENCES accounts(account_id),
    destination_account_id TEXT REFERENCES accounts(account_id),
    beneficiary_id TEXT REFERENCES beneficiaries(beneficiary_id),
    amount NUMERIC NOT NULL CHECK (amount > 0),
    currency_code TEXT NOT NULL DEFAULT 'CNY',
    fx_rate NUMERIC NOT NULL DEFAULT 1 CHECK (fx_rate > 0),
    transfer_type TEXT NOT NULL CHECK (transfer_type IN ('INTERNAL','EXTERNAL','SCHEDULED','SPLIT')),
    transfer_status TEXT NOT NULL CHECK (transfer_status IN ('PENDING','AWAITING_APPROVAL','PROCESSING','COMPLETED','FAILED','CANCELLED','REVERSED')),
    purpose TEXT, initiated_at TEXT NOT NULL, completed_at TEXT,
    CHECK ((destination_account_id IS NOT NULL) OR (beneficiary_id IS NOT NULL))
);
CREATE INDEX ix_transfers_source_time ON transfers(source_account_id, initiated_at DESC);

CREATE TABLE finn_transfer_intents (
    intent_id TEXT PRIMARY KEY,
    customer_id TEXT NOT NULL REFERENCES customers(customer_id),
    debtor_account_id TEXT NOT NULL REFERENCES accounts(account_id),
    creditor_name TEXT NOT NULL,
    creditor_account_number TEXT NOT NULL,
    amount NUMERIC NOT NULL CHECK (amount > 0),
    currency_code TEXT NOT NULL DEFAULT 'CNY',
    description TEXT,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    executed_at TEXT
);

CREATE TABLE transfer_authorizations (
    authorization_id TEXT PRIMARY KEY,
    transfer_id TEXT NOT NULL REFERENCES transfers(transfer_id),
    authorization_method TEXT NOT NULL CHECK (authorization_method IN ('USER_CONFIRMATION','SMS_OTP','BIOMETRIC','SECURITY_TOKEN')),
    authorization_status TEXT NOT NULL CHECK (authorization_status IN ('PENDING','APPROVED','DECLINED','EXPIRED')),
    authorized_at TEXT, expires_at TEXT, authenticator_reference TEXT
);

CREATE TABLE payment_schedules (
    schedule_id TEXT PRIMARY KEY,
    source_account_id TEXT NOT NULL REFERENCES accounts(account_id),
    beneficiary_id TEXT REFERENCES beneficiaries(beneficiary_id),
    destination_account_id TEXT REFERENCES accounts(account_id),
    amount NUMERIC NOT NULL CHECK (amount > 0), currency_code TEXT NOT NULL DEFAULT 'CNY',
    frequency TEXT NOT NULL CHECK (frequency IN ('ONCE','WEEKLY','MONTHLY','QUARTERLY','YEARLY')),
    next_execution_date TEXT NOT NULL, end_date TEXT,
    schedule_status TEXT NOT NULL DEFAULT 'ACTIVE' CHECK (schedule_status IN ('ACTIVE','PAUSED','CANCELLED','COMPLETED')),
    created_at TEXT NOT NULL
);

CREATE TABLE account_transactions (
    transaction_id TEXT PRIMARY KEY,
    account_id TEXT NOT NULL REFERENCES accounts(account_id),
    transfer_id TEXT REFERENCES transfers(transfer_id),
    transaction_type TEXT NOT NULL CHECK (transaction_type IN ('TRANSFER_IN','TRANSFER_OUT','CARD_PURCHASE','CASH_WITHDRAWAL','FEE','INTEREST','LOAN_DISBURSEMENT','LOAN_REPAYMENT','INVESTMENT_BUY','INVESTMENT_SELL','ADJUSTMENT')),
    direction TEXT NOT NULL CHECK (direction IN ('CREDIT','DEBIT')),
    amount NUMERIC NOT NULL CHECK (amount > 0), currency_code TEXT NOT NULL DEFAULT 'CNY',
    balance_after NUMERIC NOT NULL,
    transaction_status TEXT NOT NULL CHECK (transaction_status IN ('PENDING','POSTED','REVERSED','DECLINED')),
    counterparty_name TEXT, merchant_category TEXT, description TEXT,
    booked_at TEXT NOT NULL, value_date TEXT NOT NULL
);
CREATE INDEX ix_account_transactions_account_time ON account_transactions(account_id, booked_at DESC);

CREATE TABLE card_transactions (
    card_transaction_id TEXT PRIMARY KEY,
    card_id TEXT NOT NULL REFERENCES cards(card_id),
    account_transaction_id TEXT REFERENCES account_transactions(transaction_id),
    merchant_name TEXT NOT NULL, merchant_category_code TEXT, merchant_country TEXT NOT NULL DEFAULT 'CN',
    amount NUMERIC NOT NULL CHECK (amount > 0), currency_code TEXT NOT NULL DEFAULT 'CNY',
    transaction_status TEXT NOT NULL CHECK (transaction_status IN ('AUTHORIZED','SETTLED','DECLINED','REVERSED')),
    occurred_at TEXT NOT NULL, is_recurring INTEGER NOT NULL DEFAULT 0 CHECK (is_recurring IN (0,1))
);

CREATE TABLE direct_debit_mandates (
    mandate_id TEXT PRIMARY KEY,
    account_id TEXT NOT NULL REFERENCES accounts(account_id),
    merchant_name TEXT NOT NULL, mandate_reference TEXT NOT NULL UNIQUE,
    maximum_amount NUMERIC, currency_code TEXT NOT NULL DEFAULT 'CNY',
    mandate_status TEXT NOT NULL CHECK (mandate_status IN ('ACTIVE','CANCELLED','EXPIRED')),
    valid_from TEXT NOT NULL, valid_to TEXT, cancelled_at TEXT
);

CREATE TABLE subscriptions (
    subscription_id TEXT PRIMARY KEY,
    customer_id TEXT NOT NULL REFERENCES customers(customer_id),
    account_id TEXT NOT NULL REFERENCES accounts(account_id),
    card_id TEXT REFERENCES cards(card_id),
    mandate_id TEXT REFERENCES direct_debit_mandates(mandate_id),
    merchant_name TEXT NOT NULL, category TEXT NOT NULL,
    typical_amount NUMERIC NOT NULL CHECK (typical_amount > 0), currency_code TEXT NOT NULL DEFAULT 'CNY',
    billing_frequency TEXT NOT NULL CHECK (billing_frequency IN ('WEEKLY','MONTHLY','QUARTERLY','YEARLY')),
    next_renewal_date TEXT, subscription_status TEXT NOT NULL DEFAULT 'ACTIVE'
        CHECK (subscription_status IN ('DETECTED','ACTIVE','CANCELLATION_PENDING','CANCELLED')),
    detected_at TEXT NOT NULL, cancelled_at TEXT
);

CREATE TABLE loans (
    loan_id TEXT PRIMARY KEY,
    loan_number TEXT NOT NULL UNIQUE, product_name TEXT NOT NULL,
    principal_amount NUMERIC NOT NULL CHECK (principal_amount > 0),
    outstanding_principal NUMERIC NOT NULL CHECK (outstanding_principal >= 0),
    currency_code TEXT NOT NULL DEFAULT 'CNY', annual_interest_rate NUMERIC NOT NULL CHECK (annual_interest_rate >= 0),
    repayment_frequency TEXT NOT NULL CHECK (repayment_frequency IN ('MONTHLY','QUARTERLY')),
    loan_status TEXT NOT NULL CHECK (loan_status IN ('PENDING','ACTIVE','DELINQUENT','PAID_OFF','CLOSED')),
    disbursed_at TEXT, maturity_date TEXT NOT NULL
);

CREATE TABLE loan_borrowers (
    loan_id TEXT NOT NULL REFERENCES loans(loan_id),
    customer_id TEXT NOT NULL REFERENCES customers(customer_id),
    borrower_role TEXT NOT NULL CHECK (borrower_role IN ('PRIMARY','CO_BORROWER','GUARANTOR')),
    PRIMARY KEY (loan_id, customer_id)
);

CREATE TABLE loan_repayments (
    repayment_id TEXT PRIMARY KEY,
    loan_id TEXT NOT NULL REFERENCES loans(loan_id),
    paid_from_account_id TEXT REFERENCES accounts(account_id),
    due_date TEXT NOT NULL, paid_at TEXT,
    principal_component NUMERIC NOT NULL DEFAULT 0 CHECK (principal_component >= 0),
    interest_component NUMERIC NOT NULL DEFAULT 0 CHECK (interest_component >= 0),
    repayment_status TEXT NOT NULL CHECK (repayment_status IN ('DUE','PAID','OVERDUE','WAIVED'))
);

CREATE TABLE risk_assessments (
    assessment_id TEXT PRIMARY KEY,
    customer_id TEXT NOT NULL REFERENCES customers(customer_id),
    risk_profile TEXT NOT NULL CHECK (risk_profile IN ('CONSERVATIVE','BALANCED','GROWTH','AGGRESSIVE')),
    score INTEGER NOT NULL CHECK (score BETWEEN 1 AND 100),
    assessed_at TEXT NOT NULL, expires_at TEXT NOT NULL, status TEXT NOT NULL CHECK (status IN ('VALID','EXPIRED'))
);

CREATE TABLE investment_products (
    product_id TEXT PRIMARY KEY, product_code TEXT NOT NULL UNIQUE, product_name TEXT NOT NULL,
    product_type TEXT NOT NULL CHECK (product_type IN ('FUND','BOND','DEPOSIT','WEALTH_MANAGEMENT')),
    currency_code TEXT NOT NULL DEFAULT 'CNY', risk_level TEXT NOT NULL CHECK (risk_level IN ('LOW','MEDIUM','HIGH')),
    minimum_investment NUMERIC NOT NULL CHECK (minimum_investment >= 0), product_status TEXT NOT NULL CHECK (product_status IN ('OPEN','CLOSED'))
);

CREATE TABLE investment_holdings (
    holding_id TEXT PRIMARY KEY, customer_id TEXT NOT NULL REFERENCES customers(customer_id),
    product_id TEXT NOT NULL REFERENCES investment_products(product_id), funding_account_id TEXT REFERENCES accounts(account_id),
    units NUMERIC NOT NULL CHECK (units >= 0), average_cost NUMERIC NOT NULL CHECK (average_cost >= 0), market_value NUMERIC NOT NULL CHECK (market_value >= 0),
    opened_at TEXT NOT NULL, holding_status TEXT NOT NULL CHECK (holding_status IN ('ACTIVE','CLOSED'))
);

CREATE TABLE investment_orders (
    order_id TEXT PRIMARY KEY, holding_id TEXT REFERENCES investment_holdings(holding_id),
    customer_id TEXT NOT NULL REFERENCES customers(customer_id), product_id TEXT NOT NULL REFERENCES investment_products(product_id),
    order_type TEXT NOT NULL CHECK (order_type IN ('SUBSCRIBE','REDEEM')),
    amount NUMERIC NOT NULL CHECK (amount > 0), currency_code TEXT NOT NULL DEFAULT 'CNY',
    order_status TEXT NOT NULL CHECK (order_status IN ('PENDING','COMPLETED','FAILED','CANCELLED')), placed_at TEXT NOT NULL, completed_at TEXT
);

CREATE TABLE authentication_factors (
    factor_id TEXT PRIMARY KEY, customer_id TEXT NOT NULL REFERENCES customers(customer_id),
    factor_type TEXT NOT NULL CHECK (factor_type IN ('PASSWORD','SMS_OTP','BIOMETRIC','SECURITY_TOKEN')),
    factor_status TEXT NOT NULL CHECK (factor_status IN ('ACTIVE','DISABLED','LOCKED')), enrolled_at TEXT NOT NULL, last_used_at TEXT
);

CREATE TABLE agent_operations (
    operation_id TEXT PRIMARY KEY, customer_id TEXT NOT NULL REFERENCES customers(customer_id),
    operation_type TEXT NOT NULL, risk_level TEXT NOT NULL CHECK (risk_level IN ('GREEN','YELLOW','RED')),
    operation_status TEXT NOT NULL CHECK (operation_status IN ('PLANNED','AWAITING_CONFIRMATION','AWAITING_VERIFICATION','EXECUTED','FAILED','CANCELLED','ROLLED_BACK')),
    intent_summary TEXT NOT NULL, decision_trace TEXT NOT NULL, requested_at TEXT NOT NULL, executed_at TEXT
);

CREATE TABLE operation_approvals (
    approval_id TEXT PRIMARY KEY, operation_id TEXT NOT NULL REFERENCES agent_operations(operation_id),
    approval_method TEXT NOT NULL CHECK (approval_method IN ('USER_CONFIRMATION','SMS_OTP','BIOMETRIC','SECURITY_TOKEN')),
    approval_status TEXT NOT NULL CHECK (approval_status IN ('PENDING','APPROVED','DECLINED','EXPIRED')), approved_at TEXT
);

CREATE TABLE audit_logs (
    audit_id TEXT PRIMARY KEY, customer_id TEXT REFERENCES customers(customer_id),
    operation_id TEXT REFERENCES agent_operations(operation_id), transfer_id TEXT REFERENCES transfers(transfer_id),
    event_type TEXT NOT NULL, actor_type TEXT NOT NULL CHECK (actor_type IN ('CUSTOMER','AGENT','SYSTEM','STAFF')),
    outcome TEXT NOT NULL CHECK (outcome IN ('SUCCESS','FAILURE','BLOCKED')), event_at TEXT NOT NULL, details TEXT NOT NULL
);

CREATE TRIGGER prevent_posted_transaction_update
BEFORE UPDATE ON account_transactions
WHEN OLD.transaction_status = 'POSTED'
BEGIN SELECT RAISE(ABORT, 'Posted ledger entries are immutable'); END;

CREATE TRIGGER prevent_posted_transaction_delete
BEFORE DELETE ON account_transactions
WHEN OLD.transaction_status = 'POSTED'
BEGIN SELECT RAISE(ABORT, 'Posted ledger entries cannot be deleted'); END;
"""


def execute_many(cur: sqlite3.Cursor, sql: str, rows: list[tuple]) -> None:
    cur.executemany(sql, rows)


def build_database() -> None:
    DB_PATH.parent.mkdir(exist_ok=True)
    if DB_PATH.exists():
        DB_PATH.unlink()
    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.cursor()
        cur.executescript(SCHEMA)
        now = datetime(2026, 11, 2, 9, 0, 0).isoformat(sep=" ")
        today = date(2026, 11, 2)
        customer_rows = [
            ('CUS001','C202600001','Li Wei','1988-03-12','1101********0312','Shanghai'),
            ('CUS002','C202600002','Wang Fang','1991-07-28','3101********0728','Shanghai'),
            ('CUS003','C202600003','Zhang Min','1985-11-04','3205********1104','Suzhou'),
            ('CUS004','C202600004','Chen Jie','1993-01-19','4403********0119','Shenzhen'),
            ('CUS005','C202600005','Liu Yang','1987-09-16','5101********0916','Chengdu'),
            ('CUS006','C202600006','Zhao Lin','1995-05-23','4201********0523','Wuhan'),
            ('CUS007','C202600007','Sun Mei','1989-12-08','3301********1208','Hangzhou'),
            ('CUS008','C202600008','Zhou Tao','1984-04-30','1101********0430','Beijing'),
            ('CUS009','C202600009','Wu Qian','1992-08-14','4401********0814','Guangzhou'),
            ('CUS010','C202600010','Xu Bo','1986-02-26','6101********0226','Xi’an'),
        ]
        execute_many(cur, "INSERT INTO customers VALUES (?,?,?,?,?,'CN','CN','VERIFIED','ACTIVE',?,?)", [(*r[:5], now, now) for r in customer_rows])
        execute_many(cur, "INSERT INTO customer_addresses VALUES (?,?, 'HOME', ?, ?, ?, '200000', 'CN', 1)", [(f'ADR{i:03}', r[0], f'{100+i} Example Road', r[5], r[5]) for i, r in enumerate(customer_rows, 1)])
        execute_many(cur, "INSERT INTO customer_contacts VALUES (?,?, 'MOBILE', ?, 1, 1)", [(f'CON{i:03}', r[0], f'1380000{i:04}') for i, r in enumerate(customer_rows, 1)])

        accounts = [
            ('ACC001','6222026000000001','CURRENT','Everyday Current','ACTIVE',25000,25000),
            ('ACC002','6222026000000002','SAVINGS','Flexible Savings','ACTIVE',80000,80000),
            ('ACC003','6222026000000003','CURRENT','Everyday Current','ACTIVE',42000,42000),
            ('ACC004','6222026000000004','SAVINGS','Flexible Savings','ACTIVE',125000,125000),
            ('ACC005','6222026000000005','CURRENT','Everyday Current','ACTIVE',18600,18600),
            ('ACC006','6222026000000006','CURRENT','Everyday Current','ACTIVE',65000,65000),
            ('ACC007','6222026000000007','SAVINGS','Flexible Savings','ACTIVE',93000,93000),
            ('ACC008','6222026000000008','CURRENT','Everyday Current','ACTIVE',31750,31750),
            ('ACC009','6222026000000009','CURRENT','Everyday Current','ACTIVE',22500,22500),
            ('ACC010','6222026000000010','SAVINGS','Flexible Savings','ACTIVE',150000,150000),
            ('ACC011','6222026000000011','CURRENT','Everyday Current','ACTIVE',56000,56000),
            ('ACC012','6222026000000012','CURRENT','Everyday Current','ACTIVE',28000,28000),
        ]
        execute_many(cur, "INSERT INTO accounts VALUES (?,?,?,?,'CNY',?, '2024-01-15',NULL,0,?,?)", accounts)
        holder_rows = [(f'ACC{i:03}', f'CUS{i:03}', 'PRIMARY', 100, '2024-01-15') for i in range(1, 11)] + [('ACC011','CUS001','PRIMARY',50,'2024-06-01'),('ACC011','CUS002','JOINT',50,'2024-06-01'),('ACC012','CUS005','PRIMARY',100,'2024-07-01')]
        execute_many(cur, "INSERT INTO account_holders VALUES (?,?,?,?,?)", holder_rows)
        card_rows = [(f'CARD{i:03}', f'ACC{i:03}', f'CUS{i:03}', f'TOK-CNY-{i:04}', f'{1000+i:04}', 'DEBIT', 'PHYSICAL', 'ACTIVE', '2025-01-01','2029-12-31','2025-01-02',50000,5000) for i in range(1,11)]
        card_rows += [('CARD011','ACC001','CUS001','TOK-CNY-0011','1011','DEBIT','VIRTUAL','ACTIVE','2026-01-01','2030-12-31','2026-01-01',10000,0),('CARD012','ACC011','CUS002','TOK-CNY-0012','1012','DEBIT','PHYSICAL','ACTIVE','2025-06-01','2029-12-31','2025-06-02',50000,5000)]
        execute_many(cur, "INSERT INTO cards VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", card_rows)
        execute_many(cur, "INSERT INTO card_events VALUES (?,?,?,?,?,?)", [(f'CE{i:03}', r[0], 'ISSUED', r[8], 'SYSTEM', 'Initial issue') for i,r in enumerate(card_rows,1)])

        cur.execute("INSERT INTO beneficiaries VALUES ('BEN001','CUS001','Wang Fang','FINN Bank','Wang Fang','****0003','FINNCN01','CNY','INTERNAL','VERIFIED',?)", (now,))
        cur.execute("INSERT INTO beneficiaries VALUES ('BEN002','CUS005','Shenzhen Utilities','City Utilities','Shenzhen Utilities','****8291','CITZCN01','CNY','EXTERNAL','VERIFIED',?)", (now,))
        transfers = [
            ('TRF001','FINN-20261101-001','ACC001','ACC003',None,1200,'INTERNAL','COMPLETED','Dinner reimbursement','2026-11-01 19:30:00','2026-11-01 19:30:04'),
            ('TRF002','FINN-20261102-001','ACC005',None,'BEN002',286.5,'EXTERNAL','COMPLETED','October utilities','2026-11-02 08:20:00','2026-11-02 08:20:12'),
        ]
        execute_many(cur, "INSERT INTO transfers VALUES (?,?,?,?,?,?, 'CNY',1,?,?,?,?,?)", transfers)
        execute_many(cur, "INSERT INTO transfer_authorizations VALUES (?,?,?,?,?,?,?)", [('AUTH001','TRF001','USER_CONFIRMATION','APPROVED','2026-11-01 19:29:58','2026-11-01 19:31:00','CONF-001'),('AUTH002','TRF002','USER_CONFIRMATION','APPROVED','2026-11-02 08:19:55','2026-11-02 08:21:00','CONF-002')])
        ledger = [
            ('TXN001','ACC001','TRF001','TRANSFER_OUT','DEBIT',1200,23800,'POSTED','Wang Fang',None,'Dinner reimbursement','2026-11-01 19:30:04'),
            ('TXN002','ACC003','TRF001','TRANSFER_IN','CREDIT',1200,42000,'POSTED','Li Wei',None,'Dinner reimbursement','2026-11-01 19:30:04'),
            ('TXN003','ACC005','TRF002','TRANSFER_OUT','DEBIT',286.5,18600,'POSTED','Shenzhen Utilities',None,'October utilities','2026-11-02 08:20:12'),
            ('TXN004','ACC001',None,'CARD_PURCHASE','DEBIT',68.5,25000,'POSTED','Green Tea Cafe','5812','Coffee and lunch','2026-11-02 08:10:00'),
            ('TXN005','ACC007',None,'INTEREST','CREDIT',210,93000,'POSTED','FINN Bank',None,'Monthly savings interest','2026-11-01 00:00:00'),
        ]
        execute_many(cur, "INSERT INTO account_transactions VALUES (?,?,?,?,?,?, 'CNY', ?, ?, ?, ?, ?, ?, ?)", [(a,b,c,d,e,f,g,h,i,j,k,l,l[:10]) for a,b,c,d,e,f,g,h,i,j,k,l in ledger])
        cur.execute("INSERT INTO card_transactions VALUES ('CTX001','CARD001','TXN004','Green Tea Cafe','5812','CN',68.5,'CNY','SETTLED','2026-11-02 08:10:00',0)")
        cur.execute("INSERT INTO direct_debit_mandates VALUES ('MAN001','ACC005','Shenzhen Utilities','MAND-2026-0001',500,'CNY','ACTIVE','2025-01-01',NULL,NULL)")
        cur.execute("INSERT INTO subscriptions VALUES ('SUB001','CUS001','ACC001','CARD011',NULL,'Cloud Storage','Software',25,'CNY','MONTHLY','2026-11-15','ACTIVE','2026-04-15',NULL)")
        cur.execute("INSERT INTO subscriptions VALUES ('SUB002','CUS005','ACC005',NULL,'MAN001','Shenzhen Utilities','Utilities',286.5,'CNY','MONTHLY','2026-12-02','ACTIVE','2026-06-02',NULL)")

        cur.execute("INSERT INTO loans VALUES ('LOAN001','LN202600001','Personal Term Loan',100000,72000,'CNY',0.048,'MONTHLY','ACTIVE','2025-02-01','2030-02-01')")
        cur.execute("INSERT INTO loan_borrowers VALUES ('LOAN001','CUS004','PRIMARY')")
        cur.execute("INSERT INTO loan_repayments VALUES ('REP001','LOAN001','ACC006','2026-11-05',NULL,1500,288,'DUE')")
        execute_many(cur, "INSERT INTO risk_assessments VALUES (?,?,?,?,?,?,?)", [('RISK001','CUS001','BALANCED',55,'2026-06-01','2027-06-01','VALID'),('RISK002','CUS007','CONSERVATIVE',30,'2026-08-15','2027-08-15','VALID')])
        execute_many(cur, "INSERT INTO investment_products VALUES (?,?,?,?,?,?,?,?)", [('PROD001','FND-BAL-001','Balanced Growth Fund','FUND','CNY','MEDIUM',100,'OPEN'),('PROD002','WMP-LOW-001','Stable Income Product','WEALTH_MANAGEMENT','CNY','LOW',1000,'OPEN')])
        cur.execute("INSERT INTO investment_holdings VALUES ('HOLD001','CUS001','PROD001','ACC002',1200,10,12600,'2026-06-10','ACTIVE')")
        cur.execute("INSERT INTO investment_orders VALUES ('ORD001','HOLD001','CUS001','PROD001','SUBSCRIBE',12000,'CNY','COMPLETED','2026-06-10 10:00:00','2026-06-10 10:00:05')")
        execute_many(cur, "INSERT INTO authentication_factors VALUES (?,?,?,?,?,?)", [(f'FAC{i:03}',f'CUS{i:03}','SMS_OTP','ACTIVE','2024-01-15',None) for i in range(1,11)])
        cur.execute("INSERT INTO agent_operations VALUES ('OP001','CUS001','TRANSFER','YELLOW','EXECUTED','Transfer CNY 1,200 to Wang Fang','Intent: transfer; threshold check: yellow; confirmation: approved','2026-11-01 19:29:30','2026-11-01 19:30:04')")
        cur.execute("INSERT INTO operation_approvals VALUES ('APR001','OP001','USER_CONFIRMATION','APPROVED','2026-11-01 19:29:58')")
        cur.execute("INSERT INTO audit_logs VALUES ('AUD001','CUS001','OP001','TRF001','TRANSFER_EXECUTED','AGENT','SUCCESS','2026-11-01 19:30:04','Transfer executed after explicit confirmation')")
        conn.commit()
    finally:
        conn.close()


if __name__ == '__main__':
    build_database()
    print(f'Created {DB_PATH}')
