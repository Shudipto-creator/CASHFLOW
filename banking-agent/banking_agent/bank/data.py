"""Seed data for the mock bank.

CNY-denominated, Chinese retail banking context. Every row is dated at least
one day in the past so that a fresh run starts with zero spend *today* — the
Yellow/Red tier rules in ``banking_agent.gate.tiers`` depend on today's
cumulative total, and the demo needs a deterministic starting point.

Category ids come from ``bank2ai.CANONICAL_CATEGORY_IDS`` so a client-side
taxonomy written against the demo keeps working against any conformant server.
"""

from datetime import date, timedelta

from bank2ai import CANONICAL_CATEGORY_IDS

_TODAY = date.today()


def _days_ago(n: int) -> str:
    return (_TODAY - timedelta(days=n)).isoformat()


# --- Accounts -------------------------------------------------------------
# `balance` and `availableBalance` are CNY. The credit card carries a negative
# balance (money owed) plus a statement summary, which also exercises the
# optional card fields on the Account model.

ACCOUNTS: list[dict] = [
    {
        "id": "acc_cmb_001",
        "name": "招商银行一卡通",
        "accountNumber": "6214 8300 1234 5678",
        "bban": "6214830012345678",
        "bic": "CMBCCNBS",
        "currency": "CNY",
        "balance": 128_450.00,
        "availableBalance": 128_450.00,
        "overdraftLimit": 0.0,
        "balances": [
            {
                "type": "ClosingBooked",
                "amount": 128_450.00,
                "currency": "CNY",
                "asOf": f"{_days_ago(1)}T15:30:00Z",
            },
            {
                "type": "InterimAvailable",
                "amount": 128_450.00,
                "currency": "CNY",
                "asOf": f"{_days_ago(1)}T15:30:00Z",
            },
        ],
        "ownerName": "张小伟",
        "product": "招商银行一卡通（金卡）",
        "status": "Enabled",
        "usage": "Private",
        "accountType": "Current",
        "isWithdrawalAccount": True,
        "isDefaultAccount": True,
        "openedDate": "2019-03-11",
        "balanceUpdatedAt": f"{_days_ago(1)}T15:30:00Z",
    },
    {
        "id": "acc_icbc_002",
        "name": "工商银行储蓄卡",
        "accountNumber": "6222 0212 3456 7890",
        "bban": "6222021234567890",
        "bic": "ICBKCNBJ",
        "currency": "CNY",
        "balance": 46_200.00,
        "availableBalance": 46_200.00,
        "overdraftLimit": 0.0,
        "ownerName": "张小伟",
        "product": "工银灵通卡",
        "status": "Enabled",
        "usage": "Private",
        "accountType": "Savings",
        "isWithdrawalAccount": True,
        "isDefaultAccount": False,
        "openedDate": "2016-08-22",
        "balanceUpdatedAt": f"{_days_ago(1)}T15:30:00Z",
    },
    {
        "id": "acc_credit_003",
        "name": "中信银行信用卡",
        "accountNumber": "6226 8888 1234 5678",
        "bban": "6226888812345678",
        "maskedPan": "622688xxxxxx5678",
        "bic": "CIBKCNBJ",
        "currency": "CNY",
        "balance": -3_280.50,
        "availableBalance": 16_719.50,
        "overdraftLimit": 20_000.0,
        "ownerName": "张小伟",
        "product": "中信银行魔力白金卡",
        "status": "Enabled",
        "usage": "Private",
        "accountType": "Credit",
        "isWithdrawalAccount": False,
        "isDefaultAccount": False,
        "openedDate": "2021-06-18",
        "balanceUpdatedAt": f"{_days_ago(1)}T15:30:00Z",
        "statementBalance": 3_280.50,
        "minimumPaymentDue": 328.05,
        "paymentDueDate": _days_ago(-12),
        "statementClosingDate": _days_ago(-5),
    },
]


# --- Transactions ---------------------------------------------------------
# Signed amounts: income is positive, spending is negative.

_TRANSACTIONS: list[dict] = [
    {
        "id": "tx_salary_001",
        "accountId": "acc_cmb_001",
        "description": "工资代发 — 北京字节跳动科技有限公司",
        "amount": 25_000.00,
        "date": _days_ago(6),
        "categoryId": "Income",
        "counterparty": {
            "name": "北京字节跳动科技有限公司",
            "accountIdentifier": {
                "type": "accountNumber",
                "accountNumber": "11000012345678901",
                "country": "CN",
            },
        },
        "properties": {
            "transactionCode": "PMNT-RCDT-SALA",
            "remittanceInformation": "工资 2026年9月",
            "endToEndId": "SALARY-202609",
        },
    },
    {
        "id": "tx_rent_001",
        "accountId": "acc_cmb_001",
        "description": "房租 — 张伟",
        "amount": -6_500.00,
        "date": _days_ago(5),
        "categoryId": "Housing",
        "counterparty": {
            "name": "张伟",
            "accountIdentifier": {
                "type": "accountNumber",
                "accountNumber": "6217 0012 3456 7890",
                "country": "CN",
            },
        },
    },
    {
        "id": "tx_grocery_001",
        "accountId": "acc_cmb_001",
        "description": "盒马鲜生",
        "amount": -386.50,
        "date": _days_ago(4),
        "categoryId": "Groceries",
    },
    {
        "id": "tx_grocery_002",
        "accountId": "acc_cmb_001",
        "description": "永辉超市",
        "amount": -212.30,
        "date": _days_ago(9),
        "categoryId": "Groceries",
    },
    {
        "id": "tx_dining_001",
        "accountId": "acc_credit_003",
        "description": "海底捞火锅",
        "amount": -458.00,
        "date": _days_ago(3),
        "categoryId": "DiningAndEntertainment",
    },
    {
        "id": "tx_dining_002",
        "accountId": "acc_credit_003",
        "description": "星巴克",
        "amount": -68.00,
        "date": _days_ago(2),
        "categoryId": "DiningAndEntertainment",
    },
    {
        "id": "tx_transport_001",
        "accountId": "acc_cmb_001",
        "description": "滴滴出行",
        "amount": -126.40,
        "date": _days_ago(2),
        "categoryId": "Transport",
    },
    {
        "id": "tx_transport_002",
        "accountId": "acc_credit_003",
        "description": "中国石化加油",
        "amount": -420.00,
        "date": _days_ago(7),
        "categoryId": "Transport",
    },
    {
        "id": "tx_utilities_001",
        "accountId": "acc_cmb_001",
        "description": "国家电网电费",
        "amount": -285.60,
        "date": _days_ago(8),
        "categoryId": "Utilities",
        "counterparty": {
            "name": "国网北京市电力公司",
            "accountIdentifier": {"type": "bban", "bban": "1100000000001", "country": "CN"},
        },
    },
    {
        "id": "tx_utilities_002",
        "accountId": "acc_cmb_001",
        "description": "中国移动话费",
        "amount": -128.00,
        "date": _days_ago(11),
        "categoryId": "Utilities",
    },
    # Subscription rows exist so the "Subscription Deduction Management"
    # scenario has something real to detect and cancel.
    {
        "id": "tx_subscription_001",
        "accountId": "acc_credit_003",
        "description": "爱奇艺会员连续包月",
        "amount": -25.00,
        "date": _days_ago(10),
        "categoryId": "Subscriptions",
        "properties": {"mandateId": "IQIYI-AUTO-20240301", "purposeCode": "SUBS"},
    },
    {
        "id": "tx_subscription_002",
        "accountId": "acc_credit_003",
        "description": "网易云音乐黑胶VIP",
        "amount": -15.00,
        "date": _days_ago(13),
        "categoryId": "Subscriptions",
        "properties": {"mandateId": "NETEASE-AUTO-20240115", "purposeCode": "SUBS"},
    },
    {
        "id": "tx_subscription_003",
        "accountId": "acc_credit_003",
        "description": "美团外卖会员",
        "amount": -12.00,
        "date": _days_ago(16),
        "categoryId": "Subscriptions",
        "properties": {"mandateId": "MEITUAN-AUTO-20240210", "purposeCode": "SUBS"},
    },
    {
        "id": "tx_health_001",
        "accountId": "acc_cmb_001",
        "description": "同仁堂药房",
        "amount": -156.80,
        "date": _days_ago(14),
        "categoryId": "Health",
    },
    {
        "id": "tx_shopping_001",
        "accountId": "acc_credit_003",
        "description": "京东商城",
        "amount": -1_288.00,
        "date": _days_ago(12),
        "categoryId": "Shopping",
    },
    {
        "id": "tx_shopping_002",
        "accountId": "acc_credit_003",
        "description": "淘宝",
        "amount": -356.90,
        "date": _days_ago(17),
        "categoryId": "Shopping",
    },
    {
        "id": "tx_transfer_001",
        "accountId": "acc_cmb_001",
        "description": "转账 — 李娜",
        "amount": -2_000.00,
        "date": _days_ago(19),
        "categoryId": "Transfer",
        "counterparty": {
            "name": "李娜",
            "accountIdentifier": {
                "type": "accountNumber",
                "accountNumber": "6225 8888 0000 1234",
                "country": "CN",
            },
        },
    },
    {
        "id": "tx_fee_001",
        "accountId": "acc_cmb_001",
        "description": "跨行转账手续费",
        "amount": -5.00,
        "date": _days_ago(19),
        "categoryId": "Fees",
    },
]


# --- Categories -----------------------------------------------------------
# Full canonical set, so a client can group by any of them.

CATEGORIES: list[dict] = [{"id": cid, "name": cid} for cid in CANONICAL_CATEGORY_IDS]


# --- Recipients -----------------------------------------------------------
# China has no IBAN, so these use the `accountNumber` and `bban` variants of
# the AccountIdentifier discriminated union (both carry an ISO 3166 `country`).

RECIPIENTS: list[dict] = [
    {
        "id": "rcpt_001",
        "name": "李娜",
        "accountIdentifier": {
            "type": "accountNumber",
            "accountNumber": "6225 8888 0000 1234",
            "country": "CN",
        },
        "nickname": "妻子",
        "isFavorite": True,
        "defaultDescription": "家庭生活费",
    },
    {
        "id": "rcpt_002",
        "name": "张伟",
        "accountIdentifier": {
            "type": "accountNumber",
            "accountNumber": "6217 0012 3456 7890",
            "country": "CN",
        },
        "nickname": "房东",
        "isFavorite": True,
        "defaultDescription": "房租",
    },
    {
        "id": "rcpt_003",
        "name": "王强",
        "accountIdentifier": {
            "type": "bban",
            "bban": "6217001234567890",
            "country": "CN",
        },
        "nickname": "同事",
        "isFavorite": False,
    },
    {
        "id": "rcpt_004",
        "name": "陈静",
        "accountIdentifier": {
            "type": "accountNumber",
            "accountNumber": "6228 4800 1111 2222",
            "country": "CN",
        },
        "nickname": "大学同学",
        "isFavorite": False,
    },
]


def transactions() -> list[dict]:
    """Return a fresh, newest-first copy of the seeded history."""
    rows = [dict(t) for t in _TRANSACTIONS]
    rows.sort(key=lambda t: t["date"], reverse=True)
    return rows
