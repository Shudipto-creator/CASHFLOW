import asyncio
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.routers import banking_agent
from app.services import cfo_intent


@pytest.mark.parametrize(
    "question",
    [
        "What is my balance?",
        "How much do I have on my account?",
        "How much do I have in my account?",
        "Show my account balance",
        "我有多少钱？",
        "我的账户余额是多少？",
    ],
)
def test_balance_question_variants_are_recognized(question):
    assert banking_agent._is_balance_question(question)


@pytest.mark.parametrize(
    "question",
    [
        "How much did I spend this month?",
        "Tell me about my subscriptions",
        "Transfer 25 to Alex",
    ],
)
def test_non_balance_questions_are_not_routed_to_balance_lookup(question):
    assert not banking_agent._is_balance_question(question)


def test_balance_chat_uses_only_the_authenticated_users_accounts(monkeypatch):
    user = SimpleNamespace(user_id="user-1")
    monkeypatch.setattr(
        banking_agent.finn_bank,
        "accounts_for",
        lambda requested_user: (
            {"items": [
                {
                    "name": "Everyday account",
                    "accountNumber": "12345678",
                    "availableBalance": 1250.5,
                    "currency": "CNY",
                },
                {
                    "name": "Savings account",
                    "accountNumber": "87654321",
                    "availableBalance": 300,
                    "currency": "CNY",
                },
                {
                    "name": "Travel account",
                    "accountNumber": "22223333",
                    "availableBalance": 40,
                    "currency": "USD",
                },
            ]}
            if requested_user is user
            else {"items": []}
        ),
    )
    monkeypatch.setattr(
        banking_agent,
        "_get_agent",
        lambda *_: pytest.fail("Balance lookup should not call the LLM agent"),
    )

    response = asyncio.run(
        banking_agent.agent_chat(
            banking_agent.AgentChatRequest(
                message="How much do I have on my account?"
            ),
            user,
        )
    )

    assert response.code == "OK"
    assert response.operation_id == "get-accounts"
    assert "Total available in CNY: 1,550.50." in response.message
    assert "Total available in USD: 40.00." in response.message
    assert "5678" in response.message
    assert response.execution == {"source": "finn", "customer_scoped": True}


def test_balance_lookup_fails_closed_for_invalid_balance(monkeypatch):
    user = SimpleNamespace(user_id="user-1")
    monkeypatch.setattr(
        banking_agent.finn_bank,
        "accounts_for",
        lambda _: {"items": [{"availableBalance": None}]},
    )

    with pytest.raises(HTTPException) as error:
        banking_agent._balance_reply(user)

    assert error.value.status_code == 503


@pytest.mark.parametrize(
    ("question", "expected_direction"),
    [
        ("What is my income?", "CREDIT"),
        ("What was my spending last month?", "DEBIT"),
        ("How much did I spend this month?", "DEBIT"),
        ("Show my income this year", "CREDIT"),
    ],
)
def test_transaction_summary_question_is_recognized(question, expected_direction):
    summary = banking_agent._transaction_summary_request(question)
    assert summary is not None
    assert summary[0] == expected_direction


def test_last_month_summary_uses_previous_calendar_month():
    today = datetime.now().date()
    previous_month_end = today.replace(day=1) - timedelta(days=1)
    previous_month_start = previous_month_end.replace(day=1)

    assert banking_agent._transaction_summary_request(
        "What was my spending last month?"
    ) == ("DEBIT", previous_month_start.isoformat(), previous_month_end.isoformat())


def test_transaction_summary_chat_uses_finndb_without_calling_llm(monkeypatch):
    user = SimpleNamespace(user_id="user-1")
    monkeypatch.setattr(
        banking_agent.finn_bank,
        "transaction_totals_for",
        lambda requested_user, direction, start_date, end_date: (
            {"items": [{"currency": "CNY", "total": 1234.5, "transaction_count": 3}]}
            if requested_user is user and direction == "CREDIT" and start_date is None and end_date is None
            else {"items": []}
        ),
    )
    monkeypatch.setattr(
        banking_agent,
        "_get_agent",
        lambda *_: pytest.fail("Transaction summary should not call the LLM tool"),
    )

    response = asyncio.run(
        banking_agent.agent_chat(
            banking_agent.AgentChatRequest(message="What is my income?"),
            user,
        )
    )

    assert response.code == "OK"
    assert response.operation_id == "get-transactions-summary"
    assert "¥1,234.50 across 3 transaction(s)" in response.message
    assert "incoming transfers" in response.message
    assert response.execution["source"] == "finn"


@pytest.mark.parametrize(
    "message",
    [
        "transfert 100 to @Chen Jie",
        "transfer 100 to @Chen Jie",
        "transferts 100 to @Chen Jie",
    ],
)
def test_transfer_spellings_are_routed_to_finn_handler(message):
    assert banking_agent._is_transfer_request(message)


def test_french_spelling_transfer_does_not_fall_through_to_postman_agent(monkeypatch):
    user = SimpleNamespace(user_id="user-1")

    async def finn_transfer(payload, requested_user, db):
        assert payload.message == "transfert 100 to @Chen Jie"
        assert requested_user is user
        return banking_agent._transfer_response("Local transfer flow", code="RECIPIENT_REQUIRED")

    monkeypatch.setattr(banking_agent, "_handle_finn_transfer", finn_transfer)
    monkeypatch.setattr(
        banking_agent,
        "_get_agent",
        lambda *_: pytest.fail("The Postman-backed agent must not handle a FINN transfer"),
    )

    response = asyncio.run(
        banking_agent.agent_chat(
            banking_agent.AgentChatRequest(message="transfert 100 to @Chen Jie"),
            user,
            None,
        )
    )

    assert response.processing_mode == "finn-direct"
    assert response.code == "RECIPIENT_REQUIRED"


def test_intent_interpreter_accepts_provider_parsed_json(monkeypatch):
    class Model:
        def invoke_agent(self, **kwargs):
            assert "minor spelling mistakes" in kwargs["system_prompt"]
            return {
                "intent": "transaction_summary",
                "confidence": 0.94,
                "direction": "CREDIT",
                "period": "last_month",
                "amount": None,
                "recipient_name": None,
                "currency": "CNY",
            }

    monkeypatch.setattr(cfo_intent, "get_llm_client", lambda _: Model())

    result = cfo_intent.interpret_cfo_intent("how much did i recive last month?")

    assert result is not None
    assert result["intent"] == "transaction_summary"
    assert result["direction"] == "CREDIT"
    assert result["period"] == "last_month"


def test_natural_transfer_wording_is_interpreted_and_validated_locally(monkeypatch):
    user = SimpleNamespace(user_id="user-1")
    parsed_intent = {
        "intent": "transfer",
        "confidence": 0.92,
        "direction": None,
        "period": "all_time",
        "amount": 100,
        "recipient_name": "Chen Jie",
        "currency": "CNY",
    }
    monkeypatch.setattr(
        banking_agent,
        "interpret_cfo_intent",
        lambda *_: parsed_intent,
    )
    observed = {}

    async def finn_transfer(payload, requested_user, db, interpreted_intent=None):
        observed["message"] = payload.message
        observed["user"] = requested_user
        observed["intent"] = interpreted_intent
        return banking_agent._transfer_response("Review transfer", code="CONFIRMATION_REQUIRED")

    monkeypatch.setattr(banking_agent, "_handle_finn_transfer", finn_transfer)
    monkeypatch.setattr(
        banking_agent,
        "_get_agent",
        lambda *_: pytest.fail("Natural transfer language must not reach the legacy executor"),
    )

    response = asyncio.run(
        banking_agent.agent_chat(
            banking_agent.AgentChatRequest(message="Would you send one hundred to Chen Jie?"),
            user,
            None,
        )
    )

    assert response.code == "CONFIRMATION_REQUIRED"
    assert observed == {
        "message": "Would you send one hundred to Chen Jie?",
        "user": user,
        "intent": parsed_intent,
    }


def test_natural_conversation_uses_interpreted_reply(monkeypatch):
    user = SimpleNamespace(user_id="user-1")
    monkeypatch.setattr(
        banking_agent,
        "interpret_cfo_intent",
        lambda *_: {
            "intent": "conversation",
            "confidence": 0.98,
            "direction": None,
            "period": "all_time",
            "amount": None,
            "recipient_name": None,
            "currency": "CNY",
            "reply": "Of course. What would you like to know?",
        },
    )
    monkeypatch.setattr(
        banking_agent,
        "_get_agent",
        lambda *_: pytest.fail("Interpreted conversation should not enter the operation selector"),
    )

    response = asyncio.run(
        banking_agent.agent_chat(
            banking_agent.AgentChatRequest(message="Can I ask you something?"),
            user,
            None,
        )
    )

    assert response.message == "Of course. What would you like to know?"
    assert response.processing_mode == "cfo-conversation"


def test_demo_mfa_challenge_uses_default_terminal_delivery(capsys):
    from app.routers.banking_agent import SmsCodeMfa

    async def create_challenge():
        verifier = SmsCodeMfa()
        challenge_id = await verifier.challenge(subject="test-user", purpose="test transfer")
        return challenge_id

    challenge_id = asyncio.run(create_challenge())
    output = capsys.readouterr().out.strip()

    prefix = f"[MFA] code for test-user ({challenge_id}): "
    assert output.startswith(prefix)
    code = output.removeprefix(prefix)
    assert len(code) == 6
    assert code.isdigit()

