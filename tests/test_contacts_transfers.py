import asyncio
import sqlite3
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import models
from app.database import Base
from app.routers import banking_agent, contacts
from app.services import finn_bank
from scripts.create_finndb import SCHEMA


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


def create_user(db, user_id, name):
    user = models.User(
        user_id=user_id,
        email=f"{user_id}@example.test",
        password_hash="test-hash",
        company_name=name,
    )
    db.add(user)
    db.commit()
    return user


def seed_finn_database(tmp_path, monkeypatch):
    database_path = tmp_path / "finndb.sqlite"
    with sqlite3.connect(database_path) as connection:
        connection.executescript(SCHEMA)
        connection.executemany(
            "INSERT INTO customers VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            [
                ("CUS001", "C0001", "Sender", "1980-01-01", "MASK1", "CN", "CN", "VERIFIED", "ACTIVE", "now", "now"),
                ("CUS002", "C0002", "Alex Chen", "1980-01-01", "MASK2", "CN", "CN", "VERIFIED", "ACTIVE", "now", "now"),
            ],
        )
        connection.executemany(
            "INSERT INTO accounts VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            [
                ("ACC001", "62220001", "CURRENT", "Sender Current", "CNY", "ACTIVE", "2024-01-01", None, 0, 1000, 1000),
                ("ACC002", "62220002", "CURRENT", "Alex Current", "CNY", "ACTIVE", "2024-01-01", None, 0, 250, 250),
            ],
        )
        connection.executemany(
            "INSERT INTO account_holders VALUES (?,?,?,?,?)",
            [
                ("ACC001", "CUS001", "PRIMARY", 100, "2024-01-01"),
                ("ACC002", "CUS002", "PRIMARY", 100, "2024-01-01"),
            ],
        )
    monkeypatch.setattr(finn_bank, "DB_PATH", database_path)
    return database_path


def test_contact_search_add_list_and_remove_are_user_scoped(db_session, monkeypatch, tmp_path):
    seed_finn_database(tmp_path, monkeypatch)
    sender = create_user(db_session, "sender", "Sender")
    target_user = create_user(db_session, "recipient-user-id", "Alex Chen")
    other = create_user(db_session, "other", "Other user")
    monkeypatch.setattr(
        contacts.finn_bank,
        "customer_id_for",
        lambda candidate: "CUS001" if candidate.user_id == sender.user_id else "CUS002",
    )

    results = contacts.search_customers("Alex", sender, db_session)["items"]
    assert results == [{"customer_id": "CUS002", "name": "Alex Chen"}]
    assert contacts.search_customers("Sender", sender, db_session)["items"] == []
    assert contacts.search_customers(target_user.user_id, sender, db_session)["items"] == []
    assert contacts.search_customers(sender.user_id, sender, db_session)["items"] == []

    preview = contacts.preview_contact_by_user_id(
        contacts.ContactUserIdCreate(user_id=target_user.user_id),
        sender,
        db_session,
    )
    assert preview == {"user_id": target_user.user_id, "name": "Alex Chen"}

    saved = contacts.add_contact_by_user_id(
        contacts.ContactUserIdCreate(user_id=target_user.user_id),
        sender,
        db_session,
    )
    assert saved["customer_id"] == "CUS002"
    assert contacts.list_contacts(sender, db_session)["items"][0]["name"] == "Alex Chen"
    assert contacts.search_customers("Alex", sender, db_session)["items"] == []
    assert contacts.search_customers(target_user.user_id, sender, db_session)["items"] == []

    with pytest.raises(HTTPException) as error:
        contacts.preview_contact_by_user_id(
            contacts.ContactUserIdCreate(user_id=target_user.user_id),
            sender,
            db_session,
        )
    assert error.value.status_code == 409

    with pytest.raises(HTTPException) as error:
        contacts.add_contact_by_user_id(
            contacts.ContactUserIdCreate(user_id=sender.user_id),
            sender,
            db_session,
        )
    assert error.value.status_code == 422

    with pytest.raises(HTTPException) as error:
        contacts.add_contact_by_user_id(
            contacts.ContactUserIdCreate(user_id="missing-user"),
            sender,
            db_session,
        )
    assert error.value.status_code == 404

    contacts.remove_contact("CUS002", sender, db_session)
    assert contacts.list_contacts(sender, db_session)["items"] == []

    saved_from_search = contacts.add_contact(
        contacts.ContactCreate(customer_id="CUS002"),
        sender,
        db_session,
    )
    assert saved_from_search["customer_id"] == "CUS002"
    contacts.remove_contact("CUS002", sender, db_session)
    assert db_session.query(models.User).filter_by(user_id=other.user_id).one()


def test_transaction_totals_are_customer_scoped_and_exclude_unposted_rows(db_session, monkeypatch, tmp_path):
    database_path = seed_finn_database(tmp_path, monkeypatch)
    sender = create_user(db_session, "sender", "Sender")
    monkeypatch.setattr(finn_bank, "customer_id_for", lambda _: "CUS001")
    transactions = [
        ("TXN-CREDIT", "ACC001", None, "TRANSFER_IN", "CREDIT", 300, "CNY", 1300,
         "POSTED", "Alex Chen", None, "Received", "2026-10-10T12:00:00", "2026-10-10"),
        ("TXN-DEBIT", "ACC001", None, "TRANSFER_OUT", "DEBIT", 125, "CNY", 1175,
         "POSTED", "Alex Chen", None, "Sent", "2026-10-15T12:00:00", "2026-10-15"),
        ("TXN-PENDING", "ACC001", None, "FEE", "DEBIT", 20, "CNY", 1155,
         "PENDING", None, None, "Pending fee", "2026-10-20T12:00:00", "2026-10-20"),
        ("TXN-OTHER-CUSTOMER", "ACC002", None, "TRANSFER_OUT", "DEBIT", 75, "CNY", 175,
         "POSTED", "Sender", None, "Other user's transfer", "2026-10-25T12:00:00", "2026-10-25"),
    ]
    with sqlite3.connect(database_path) as connection:
        connection.executemany(
            "INSERT INTO account_transactions VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            transactions,
        )

    debits = finn_bank.transaction_totals_for(sender, "DEBIT", "2026-10-01", "2026-10-31")
    credits = finn_bank.transaction_totals_for(sender, "CREDIT", "2026-10-01", "2026-10-31")

    assert debits == {"items": [{"currency": "CNY", "transaction_count": 1, "total": 125.0}]}
    assert credits == {"items": [{"currency": "CNY", "transaction_count": 1, "total": 300.0}]}


def test_smart_transfer_requires_saved_contact_and_credits_finn_account(db_session, monkeypatch, tmp_path):
    seed_finn_database(tmp_path, monkeypatch)
    sender = create_user(db_session, "sender", "Sender")
    db_session.add(models.FinnContact(user_id=sender.user_id, customer_id="CUS002"))
    db_session.commit()

    monkeypatch.setattr(banking_agent.finn_bank, "customer_id_for", lambda _: "CUS001")
    monkeypatch.setattr(banking_agent.finn_bank, "transfer_account_for", lambda _: {
        "id": "ACC001",
        "account_number": "62220001",
        "name": "Everyday Current",
        "customer_id": "CUS001",
    })
    monkeypatch.setattr(banking_agent.finn_bank, "transfer_account_for_customer", lambda customer_id: {
        "id": "ACC002",
        "account_number": "62220002",
        "name": "Everyday Current",
        "customer_id": customer_id,
    })

    prepared = {}
    executed = {}
    spend = type("SpendLedgerStub", (), {
        "spent_today": lambda self: Decimal("0"),
        "add": lambda self, amount: Decimal(amount),
    })()
    monkeypatch.setattr(banking_agent, "_finn_daily_spend", lambda _: spend)

    def prepare_transfer(user, **kwargs):
        prepared.update(kwargs)
        return "finn_intent_test"

    def execute_transfer(user, intent_id):
        executed.update({"user_id": user.user_id, "intent_id": intent_id})
        return {"transfer_id": "TRF-test", "transaction_id": "TXN-test"}

    monkeypatch.setattr(banking_agent.finn_bank, "prepare_transfer", prepare_transfer)
    monkeypatch.setattr(banking_agent.finn_bank, "execute_transfer", execute_transfer)

    first = asyncio.run(banking_agent.agent_chat(
        banking_agent.AgentChatRequest(
            message="Transfer ¥25 to @Alex Chen",
            recipient_customer_id="CUS002",
        ),
        sender,
        db_session,
    ))
    assert first.execution["needs_confirmation"] is True
    assert first.execution["transfer_preview"]["recipient_name"] == "Alex Chen"

    confirmed = asyncio.run(banking_agent.agent_chat(
        banking_agent.AgentChatRequest(
            message="Transfer ¥25 to @Alex Chen",
            recipient_customer_id="CUS002",
            confirmed=True,
            confirmation_id=first.execution["confirmation_id"],
        ),
        sender,
        db_session,
    ))
    assert confirmed.execution["needs_approval"] is True
    assert prepared["creditor_account_number"] == "62220002"
    assert prepared["creditor_customer_id"] == "CUS002"

    approval = asyncio.run(banking_agent.agent_transfer_approve(
        banking_agent.AgentTransferApprovalRequest(
            intent_id=confirmed.execution["intent_id"],
            approval_id=confirmed.execution["approval_id"],
        ),
        sender,
    ))
    assert approval["ok"] is True
    assert executed == {"user_id": sender.user_id, "intent_id": "finn_intent_test"}
    replay = asyncio.run(banking_agent.agent_chat(
        banking_agent.AgentChatRequest(
            message="Transfer ¥25 to @Alex Chen",
            recipient_customer_id="CUS002",
            confirmed=True,
            confirmation_id=first.execution["confirmation_id"],
        ),
        sender,
        db_session,
    ))
    assert replay.execution is None
    assert replay.code == "CONFIRMATION_EXPIRED"


def test_at_name_requires_disambiguation_when_saved_names_match(db_session, monkeypatch):
    sender = create_user(db_session, "sender-duplicate", "Sender")
    db_session.add_all([
        models.FinnContact(user_id=sender.user_id, customer_id="CUS001"),
        models.FinnContact(user_id=sender.user_id, customer_id="CUS002"),
    ])
    db_session.commit()
    monkeypatch.setattr(
        banking_agent.finn_bank,
        "transfer_customer",
        lambda customer_id: {"customer_id": customer_id, "name": "Wang Min"},
    )

    recipient, ambiguous = banking_agent._resolve_saved_contact(db_session, sender, "@Wang Min")

    assert recipient is None
    assert ambiguous is True
    recipient, ambiguous = banking_agent._resolve_saved_contact(
        db_session,
        sender,
        "@Wang Min",
        customer_id="CUS002",
    )
    assert recipient == {"customer_id": "CUS002", "name": "Wang Min"}
    assert ambiguous is False


def test_finn_bank_posts_sender_debit_and_recipient_credit(tmp_path, monkeypatch):
    database_path = tmp_path / "finndb.sqlite"
    with sqlite3.connect(database_path) as connection:
        connection.executescript(SCHEMA)
        customers = [
            ("CUS001", "C0001", "Sender", "1980-01-01", "MASK1", "CN", "CN", "VERIFIED", "ACTIVE", "now", "now"),
            ("CUS002", "C0002", "Recipient", "1980-01-01", "MASK2", "CN", "CN", "VERIFIED", "ACTIVE", "now", "now"),
        ]
        connection.executemany("INSERT INTO customers VALUES (?,?,?,?,?,?,?,?,?,?,?)", customers)
        accounts = [
            ("ACC001", "62220001", "CURRENT", "Sender Current", "CNY", "ACTIVE", "2024-01-01", None, 0, 1000, 1000),
            ("ACC002", "62220002", "CURRENT", "Recipient Current", "CNY", "ACTIVE", "2024-01-01", None, 0, 250, 250),
        ]
        connection.executemany("INSERT INTO accounts VALUES (?,?,?,?,?,?,?,?,?,?,?)", accounts)
        connection.executemany(
            "INSERT INTO account_holders VALUES (?,?,?,?,?)",
            [
                ("ACC001", "CUS001", "PRIMARY", 100, "2024-01-01"),
                ("ACC002", "CUS002", "PRIMARY", 100, "2024-01-01"),
            ],
        )
    monkeypatch.setattr(finn_bank, "DB_PATH", database_path)
    monkeypatch.setattr(
        finn_bank,
        "customer_id_for",
        lambda user: "CUS001" if user.user_id == "sender" else "CUS002",
    )
    sender = type("TestUser", (), {"user_id": "sender"})()
    recipient = type("TestUser", (), {"user_id": "recipient"})()

    source = finn_bank.transfer_account_for(sender)
    destination = finn_bank.transfer_account_for_customer("CUS002")
    intent_id = finn_bank.prepare_transfer(
        sender,
        debtor_account_id=source["id"],
        creditor_name="Recipient",
        creditor_account_number=destination["account_number"],
        amount=75,
        currency="CNY",
        description="Test transfer",
        creditor_customer_id="CUS002",
        require_internal=True,
    )
    result = finn_bank.execute_transfer(sender, intent_id)

    assert result["amount"] == 75
    stale_intent = finn_bank.prepare_transfer(
        sender,
        debtor_account_id=source["id"],
        creditor_name="Recipient",
        creditor_account_number=destination["account_number"],
        amount=10,
        currency="CNY",
        description="Stale recipient account",
        creditor_customer_id="CUS002",
        require_internal=True,
    )
    with sqlite3.connect(database_path) as connection:
        connection.execute("UPDATE account_holders SET customer_id='CUS001' WHERE account_id='ACC002'")
    with pytest.raises(HTTPException) as error:
        finn_bank.execute_transfer(sender, stale_intent)
    assert error.value.status_code == 409
    with sqlite3.connect(database_path) as connection:
        balances = dict(connection.execute(
            "SELECT account_id, available_balance FROM accounts"
        ).fetchall())
        transactions = connection.execute(
            "SELECT account_id, direction, amount FROM account_transactions ORDER BY account_id"
        ).fetchall()
    assert balances == {"ACC001": 925, "ACC002": 325}
    assert transactions == [("ACC001", "DEBIT", 75), ("ACC002", "CREDIT", 75)]


def test_finn_customer_mapping_prefers_matching_name_and_stays_exclusive(tmp_path, monkeypatch):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    with sqlite3.connect(tmp_path / "finndb.sqlite") as connection:
        connection.executescript(SCHEMA)
        connection.executemany(
            "INSERT INTO customers VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            [
                ("CUS001", "C0001", "Li Wei", "1980-01-01", "MASK1", "CN", "CN", "VERIFIED", "ACTIVE", "now", "now"),
                ("CUS002", "C0002", "Wang Fang", "1980-01-01", "MASK2", "CN", "CN", "VERIFIED", "ACTIVE", "now", "now"),
            ],
        )
    monkeypatch.setattr(finn_bank, "DB_PATH", tmp_path / "finndb.sqlite")
    monkeypatch.setattr(finn_bank, "SessionLocal", factory)
    session = factory()
    try:
        first = create_user(session, "user-li", "Li Wei")
        second = create_user(session, "user-wang", "Wang Fang")
        assert finn_bank.customer_id_for(first) == "CUS001"
        assert finn_bank.customer_id_for(second) == "CUS002"
        assert finn_bank.customer_id_for(first) == "CUS001"
        links = session.query(models.BankCustomerLink).order_by(models.BankCustomerLink.user_id).all()
        assert [(link.user_id, link.customer_id) for link in links] == [
            ("user-li", "CUS001"),
            ("user-wang", "CUS002"),
        ]
    finally:
        session.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


def test_daily_cumulative_limit_requires_mfa_before_preparing(db_session, monkeypatch, tmp_path, capsys):
    seed_finn_database(tmp_path, monkeypatch)
    monkeypatch.setattr(banking_agent.settings, "app_env", "development")
    sender = create_user(db_session, "sender-mfa", "Sender")
    db_session.add(models.FinnContact(user_id=sender.user_id, customer_id="CUS002"))
    db_session.commit()
    monkeypatch.setattr(banking_agent.finn_bank, "customer_id_for", lambda _: "CUS001")
    monkeypatch.setattr(banking_agent.finn_bank, "transfer_account_for", lambda user: {
        "id": "ACC001",
        "account_number": "62220001",
        "name": "Everyday Current",
        "customer_id": "CUS001",
    })
    monkeypatch.setattr(banking_agent.finn_bank, "transfer_account_for_customer", lambda customer_id: {
        "id": "ACC002",
        "account_number": "62220002",
        "name": "Everyday Current",
        "customer_id": customer_id,
    })
    spend = type("SpendLedgerStub", (), {
        "spent_today": lambda self: Decimal("900"),
        "add": lambda self, amount: Decimal("900") + Decimal(amount),
    })()
    monkeypatch.setattr(banking_agent, "_finn_daily_spend", lambda _: spend)
    challenge_calls = []
    verify_calls = []

    async def create_challenge(**kwargs):
        challenge_calls.append(kwargs)
        print(f"[MFA] code for {kwargs['subject']} (mfa-test): 123456", flush=True)
        return "mfa-test"

    async def verify_challenge(**kwargs):
        verify_calls.append(kwargs)
        return True

    monkeypatch.setattr(banking_agent._FINN_TRANSFER_MFA, "challenge", create_challenge)
    monkeypatch.setattr(banking_agent._FINN_TRANSFER_MFA, "verify", verify_challenge)
    monkeypatch.setattr(banking_agent.finn_bank, "prepare_transfer", lambda *_args, **_kwargs: "finn-mfa-intent")

    first = asyncio.run(banking_agent.agent_chat(
        banking_agent.AgentChatRequest(message="Transfer ¥200 to Alex Chen"),
        sender,
        db_session,
    ))
    assert first.execution["needs_mfa"] is True
    assert first.execution["mfa_challenge_id"] == "mfa-test"
    assert "demo_mfa_code" not in first.execution
    assert "[MFA] code for sender-mfa (mfa-test): 123456" in capsys.readouterr().out
    assert challenge_calls[0]["subject"] == sender.user_id

    confirmed = asyncio.run(banking_agent.agent_chat(
        banking_agent.AgentChatRequest(
            message="Transfer ¥200 to Alex Chen",
            confirmed=True,
            confirmation_id=first.execution["confirmation_id"],
            mfa_challenge_id="mfa-test",
            mfa_code="123456",
        ),
        sender,
        db_session,
    ))
    assert confirmed.execution["needs_approval"] is True
    assert verify_calls == [{"challenge_id": "mfa-test", "code": "123456"}]
    banking_agent._PENDING_TRANSFER_APPROVALS.pop((sender.user_id, "finn-mfa-intent"), None)
