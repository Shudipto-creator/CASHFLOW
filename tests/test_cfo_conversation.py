"""Tests for the durable FINN CFO conversation and its follow-up handling."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import models
from app.database import Base
from app.models import CfoChatMessage
from app.routers import banking_agent
from app.services import cfo_conversation, finn_bank
from app.services.llm_banking_agent import AgentResult, SelectResult


@pytest.fixture()
def db(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'app.db'}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    session = Session()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def _user(db, email="owner@example.com", name="Li Wei"):
    user = models.User(email=email, password_hash="x", company_name=name)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _chat(db, user, message, conversation_id):
    return asyncio.run(
        banking_agent.agent_chat(
            banking_agent.AgentChatRequest(
                message=message,
                conversation_id=conversation_id,
            ),
            user,
            db,
        )
    )


def test_chat_turns_are_persisted_with_their_conversation(db, monkeypatch):
    user = _user(db)
    monkeypatch.setattr(
        banking_agent.finn_bank,
        "accounts_for",
        lambda _: {
            "items": [
                {
                    "name": "Everyday Current",
                    "accountNumber": "6222026000000001",
                    "availableBalance": 25000,
                    "currency": "CNY",
                }
            ]
        },
    )

    first = _chat(db, user, "What is my balance?", "conv-persist-1")
    second = _chat(db, user, "And my balance?", "conv-persist-1")

    rows = (
        db.query(CfoChatMessage)
        .filter(CfoChatMessage.conversation_id == "conv-persist-1")
        .order_by(CfoChatMessage.id.asc())
        .all()
    )
    assert [row.role for row in rows] == ["user", "assistant", "user", "assistant"]
    assert rows[1].intent == "balance"
    assert rows[3].intent == "balance"
    assert first.conversation_id == second.conversation_id == "conv-persist-1"
    assert first.language == "en"


def test_conversation_history_is_scoped_to_the_authenticated_user(db):
    owner = _user(db, "owner@example.com")
    other = _user(db, "other@example.com")
    cfo_conversation.append_message(
        db,
        user_id=owner.user_id,
        conversation_id="conv-shared",
        role="user",
        content="my private balance question",
    )

    assert [
        item["content"]
        for item in cfo_conversation.load_history(
            db, user_id=owner.user_id, conversation_id="conv-shared"
        )
    ] == ["my private balance question"]
    assert (
        cfo_conversation.load_history(
            db, user_id=other.user_id, conversation_id="conv-shared"
        )
        == []
    )

    response = asyncio.run(
        banking_agent.get_agent_chat_history("conv-shared", 200, other, db)
    )
    assert response["messages"] == []


def test_follow_up_passes_durable_history_to_the_intent_model(db, monkeypatch):
    user = _user(db)
    captured = {}

    def fake_interpret(message, mode=None, history=None, language=None):
        captured["message"] = message
        captured["history"] = history
        captured["language"] = language
        return {
            "intent": "other",
            "confidence": 0.9,
            "direction": None,
            "period": "all_time",
            "amount": None,
            "recipient_name": None,
            "currency": "CNY",
            "reply": "I can help with FINN accounts.",
        }

    monkeypatch.setattr(banking_agent, "interpret_cfo_intent", fake_interpret)
    monkeypatch.setattr(
        banking_agent,
        "_get_agent",
        lambda *_: pytest.fail("Out-of-scope replies must not reach the bank agent"),
    )

    _chat(db, user, "Tell me about my money", "conv-memory")
    _chat(db, user, "and what about last month?", "conv-memory")

    assert captured["message"] == "and what about last month?"
    assert any(
        "Tell me about my money" in (item.get("content") or "")
        for item in captured["history"]
    )
    assert captured["language"] == "en"


def test_follow_up_inherits_previous_transaction_direction_without_llm(db, monkeypatch):
    user = _user(db)
    calls = []

    def fake_totals(requested_user, direction, start_date, end_date):
        calls.append((direction, start_date, end_date))
        return {"items": [{"currency": "CNY", "total": 120.0, "transaction_count": 2}]}

    monkeypatch.setattr(banking_agent.finn_bank, "transaction_totals_for", fake_totals)
    monkeypatch.setattr(
        banking_agent,
        "_get_agent",
        lambda *_: pytest.fail("A deterministic follow-up must not call the LLM agent"),
    )
    monkeypatch.setattr(
        banking_agent,
        "interpret_cfo_intent",
        lambda *a, **k: pytest.fail("A deterministic follow-up must not need the LLM"),
    )

    first = _chat(db, user, "How much did I spend this month?", "conv-follow")
    second = _chat(db, user, "and last month?", "conv-follow")

    today = datetime.now().date()
    previous_end = today.replace(day=1) - timedelta(days=1)
    previous_start = previous_end.replace(day=1)

    assert first.operation_id == "get-transactions-summary"
    assert second.operation_id == "get-transactions-summary"
    assert calls[0][0] == "DEBIT"
    assert calls[1] == ("DEBIT", previous_start.isoformat(), previous_end.isoformat())
    assert second.execution["direction"] == "DEBIT"


def test_chinese_balance_and_spending_answers_are_localized(db, monkeypatch):
    user = _user(db, "li@example.com", "Li Wei")
    monkeypatch.setattr(
        banking_agent.finn_bank,
        "accounts_for",
        lambda _: {
            "items": [
                {
                    "name": "Everyday Current",
                    "accountNumber": "6222026000000001",
                    "availableBalance": 25000,
                    "currency": "CNY",
                }
            ]
        },
    )
    monkeypatch.setattr(
        banking_agent.finn_bank,
        "transaction_totals_for",
        lambda *args: {
            "items": [{"currency": "CNY", "total": 88.5, "transaction_count": 3}]
        },
    )

    balance = _chat(db, user, "我的账户余额是多少？", "conv-zh")
    spending = _chat(db, user, "我这个月花了多少钱？", "conv-zh")

    assert balance.language == "zh"
    assert "您的可用余额" in balance.message
    assert "尾号 0001" in balance.message
    assert spending.language == "zh"
    assert "已记录支出" in spending.message
    assert "3 笔交易" in spending.message


def test_chinese_period_follow_up_keeps_the_spending_topic(db, monkeypatch):
    user = _user(db)
    calls = []
    monkeypatch.setattr(
        banking_agent.finn_bank,
        "transaction_totals_for",
        lambda _user, direction, start_date, end_date: calls.append(
            (direction, start_date, end_date)
        )
        or {"items": [{"currency": "CNY", "total": 10.0, "transaction_count": 1}]},
    )
    monkeypatch.setattr(
        banking_agent,
        "interpret_cfo_intent",
        lambda *a, **k: pytest.fail("Chinese follow-up must resolve without the LLM"),
    )

    _chat(db, user, "我这个月花了多少钱？", "conv-zh-follow")
    follow_up = _chat(db, user, "上个月呢？", "conv-zh-follow")

    today = datetime.now().date()
    previous_end = today.replace(day=1) - timedelta(days=1)
    previous_start = previous_end.replace(day=1)

    assert calls[1] == ("DEBIT", previous_start.isoformat(), previous_end.isoformat())
    assert follow_up.language == "zh"
    assert "已记录支出" in follow_up.message


@pytest.mark.parametrize(
    ("message", "expected_language", "fragment"),
    [
        ("What's the weather in Paris?", "en", "FINN accounts"),
        ("今天巴黎天气怎么样？", "zh", "无法回答"),
    ],
)
def test_out_of_scope_questions_are_answered_in_the_users_language(
    db, monkeypatch, message, expected_language, fragment
):
    user = _user(db)

    class StubAgent:
        async def handle(self, *args, **kwargs):
            return AgentResult(
                implemented=False,
                code="NOT_IMPLEMENTED",
                operation_id=None,
                message="not implemented",
                selected=SelectResult(
                    operation_id=None,
                    not_implemented=True,
                    rationale="no registered operation matched",
                ),
            )

    monkeypatch.setattr(banking_agent, "interpret_cfo_intent", lambda *a, **k: None)
    monkeypatch.setattr(banking_agent, "_get_agent", lambda *_: StubAgent())

    response = _chat(db, user, message, "conv-scope")

    assert response.code == "OUT_OF_SCOPE"
    assert response.language == expected_language
    assert fragment in response.message
    assert "not implemented yet" not in response.message


@pytest.mark.parametrize(
    ("message", "expected_language", "fragment"),
    [
        ("Hello", "en", "I'm FINN"),
        ("你好", "zh", "我是 FINN"),
    ],
)
def test_greetings_are_answered_without_an_llm(
    db, monkeypatch, message, expected_language, fragment
):
    user = _user(db)
    monkeypatch.setattr(
        banking_agent,
        "interpret_cfo_intent",
        lambda *a, **k: pytest.fail("A greeting must not call the LLM"),
    )

    response = _chat(db, user, message, "conv-greeting")

    assert response.code == "GREETING"
    assert response.language == expected_language
    assert fragment in response.message


def test_language_and_follow_up_helpers():
    assert cfo_conversation.detect_language("我的余额") == "zh"
    assert cfo_conversation.detect_language("balance") == "en"
    assert cfo_conversation.is_follow_up("and last month?")
    assert cfo_conversation.is_follow_up("上个月呢？")
    assert cfo_conversation.is_follow_up("transfer 20 to @Chen Jie") is False
    assert cfo_conversation.period_from_message("what about last month?") == "last_month"
    assert cfo_conversation.period_from_message("今年") == "this_year"


def test_accounts_and_transactions_are_scoped_to_the_linked_finn_customer(
    db, monkeypatch
):
    """FINNDB rows are filtered by account_holders for the user's linked customer."""
    Session = sessionmaker(bind=db.get_bind())
    monkeypatch.setattr(finn_bank, "SessionLocal", Session)
    monkeypatch.setattr(finn_bank, "DB_PATH", Path("data/finndb.sqlite").resolve())

    li_wei = _user(db, "li.wei@example.com", "Li Wei")
    wang_fang = _user(db, "wang.fang@example.com", "Wang Fang")

    li_accounts = {item["accountNumber"] for item in finn_bank.accounts_for(li_wei)["items"]}
    wang_accounts = {item["accountNumber"] for item in finn_bank.accounts_for(wang_fang)["items"]}

    assert "6222026000000001" in li_accounts  # ACC001, CUS001
    assert "6222026000000002" in wang_accounts  # ACC002, CUS002
    assert "6222026000000002" not in li_accounts
    assert "6222026000000001" not in wang_accounts

    li_transactions = finn_bank.transactions_for(li_wei, 500)["items"]
    wang_transactions = finn_bank.transactions_for(wang_fang, 500)["items"]

    assert all(item["accountId"] in {"ACC001", "ACC011"} for item in li_transactions)
    assert all(item["accountId"] in {"ACC002", "ACC011"} for item in wang_transactions)


def test_wrong_language_model_reply_is_replaced_with_a_localized_answer(db, monkeypatch):
    user = _user(db)
    monkeypatch.setattr(
        banking_agent,
        "interpret_cfo_intent",
        lambda *a, **k: {
            "intent": "conversation",
            "confidence": 0.9,
            "direction": None,
            "period": "all_time",
            "amount": None,
            "recipient_name": None,
            "currency": "CNY",
            "reply": "好的，我可以帮你。",
        },
    )

    english = _chat(db, user, "I run a small bakery", "conv-language-en")
    assert english.language == "en"
    assert english.message.startswith("I'm here to help")
    assert not any("\u4e00" <= char <= "\u9fff" for char in english.message)

    monkeypatch.setattr(
        banking_agent,
        "interpret_cfo_intent",
        lambda *a, **k: {
            "intent": "conversation",
            "confidence": 0.9,
            "direction": None,
            "period": "all_time",
            "amount": None,
            "recipient_name": None,
            "currency": "CNY",
            "reply": "I'm here to help.",
        },
    )

    chinese = _chat(db, user, "我开了一家面包店", "conv-language-zh")
    assert chinese.language == "zh"
    assert "我在" in chinese.message
