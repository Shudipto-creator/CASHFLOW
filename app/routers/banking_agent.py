"""REST bridge to the LLM banking agent (Scenario 1: Smart Transfer).

Lets a caller "send a message to the agent" over HTTP:

    POST /api/banking/agent/chat  {"message": "transfer ¥600 to 李娜"}

The agent maps the message onto a *registered, implemented* banking operation
(using RAG over the operations catalog to stay in context), hard-guards the
choice against the registry so the LLM can never invent an operation, and — for
implemented operations only — executes it through the Zero-Trust banking gate.

Authentication: JWT (``get_current_user``), matching the Ask-CFO chat rather
than the signed banking endpoints. The operations the agent runs are themselves
enforced by the banking gate (tiers / MFA / confirmation / okgate caps /
approvals / audit).
"""

from __future__ import annotations

import logging
import hashlib
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app import models
from app.dependencies import get_current_user
from app.config import get_settings
from app.services.mode_service import resolve_mode
from app.services.llm_banking_agent import BankingExecutor, LLMBankingAgent, AgentResult

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/banking", tags=["banking-agent"])
settings = get_settings()

#: Repo root = banking-agent/ lives one level up from app/.
REPO_ROOT = Path(__file__).resolve().parents[2]
POLICY = REPO_ROOT / "banking-agent" / "okgate.yaml"
GATE_ROOT = REPO_ROOT / "banking-agent"
STATE_DIR = GATE_ROOT / ".state"
VECTOR_STORE_DIR = REPO_ROOT / "data" / "vector_store"


class AgentChatRequest(BaseModel):
    message: str = Field(..., min_length=1)
    processing_mode: Optional[str] = None  # "aws" | "local" | None (global default)
    confirmed: bool = False                # answer a Yellow confirmation prompt
    mfa_challenge_id: Optional[str] = None
    mfa_code: Optional[str] = None


class AgentChatResponse(BaseModel):
    implemented: bool
    code: str
    operation_id: Optional[str] = None
    message: str
    rationale: Optional[str] = None
    proposed_operation_id: Optional[str] = None
    retrieved_operations: list[str] = []
    execution: Optional[dict[str, Any]] = None
    processing_mode: Optional[str] = None


#: Process-lifetime agent cache: one agent per processing mode.
_AGENT_CACHE: dict[str, LLMBankingAgent] = {}


def _user_scope(user: models.User) -> str:
    """Use an opaque, filesystem-safe scope for per-user gate state."""
    return hashlib.sha256(str(user.user_id).encode("utf-8")).hexdigest()[:20]


def _get_agent(mode: str, user: models.User) -> LLMBankingAgent:
    scope = _user_scope(user)
    cache_key = f"{scope}:{mode}"
    agent = _AGENT_CACHE.get(cache_key)
    if agent is None:
        user_state = STATE_DIR / scope
        agent = LLMBankingAgent.build(
            policy=POLICY,
            root=GATE_ROOT,
            state_dir=user_state,
            persist_dir=VECTOR_STORE_DIR,
            subject=str(user.user_id),
            run_id=f"llm-agent-{scope}-{mode}",
            use_llm=True,
        )
        _AGENT_CACHE[cache_key] = agent
        logger.info("Built LLM banking agent (mode=%s)", mode)
    return agent


@router.get("/demo-data")
async def demo_bank_data(user: models.User = Depends(get_current_user)):
    """Return the seeded demo accounts and activity through the policy gate.

    This is explicitly sandbox data shared by the mock bank, not an account
    opened for the authenticated CASHFLOW user. Reads still pass through
    SecureBankGate and okgate.
    """
    if settings.app_env.lower() in {"production", "staging"}:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Demo bank data is disabled outside development.",
        )
    scope = _user_scope(user)
    user_state = STATE_DIR / scope
    executor = BankingExecutor(
        policy=POLICY,
        root=GATE_ROOT,
        state_dir=user_state,
        subject=str(user.user_id),
        run_id=f"demo-read-{scope}",
    )
    from banking_agent.gate import DailySpendLedger, GateClient, SecureBankGate

    client = GateClient(
        policy=POLICY,
        root=GATE_ROOT,
        run_id=f"demo-read-{scope}",
        npx=executor._npx_for_gate(),
    )
    try:
        await client.open()
        gate = SecureBankGate(
            client=client,
            spend=DailySpendLedger(user_state / "daily_spend.json"),
            subject=str(user.user_id),
        )
        accounts = await gate.call("get-accounts")
        transactions = await gate.call(
            "get-transactions", {"count": 10, "order": "NewestFirst", "verbosity": "minimal"}
        )
    except Exception as exc:
        logger.exception("Could not load demo bank data for user %s", user.user_id)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The demo bank is unavailable. Please try again.",
        ) from exc
    finally:
        await client.close()

    if not accounts.ok or not transactions.ok:
        detail = accounts.message if not accounts.ok else transactions.message
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=detail or "The demo bank refused the read.")

    return {
        "source": "demo_sandbox",
        "accounts": accounts.value or {},
        "transactions": transactions.value or {},
    }


@router.post("/agent/chat", response_model=AgentChatResponse)
async def agent_chat(
    payload: AgentChatRequest,
    user: models.User = Depends(get_current_user),
):
    """Send a message to the LLM banking agent and get its action back."""
    mode = resolve_mode(payload.processing_mode)
    agent = _get_agent(mode, user)

    result: AgentResult = await agent.handle(
        payload.message,
        confirmed=payload.confirmed,
        mfa_challenge_id=payload.mfa_challenge_id,
        mfa_code=payload.mfa_code,
    )

    return AgentChatResponse(
        implemented=result.implemented,
        code=result.code,
        operation_id=result.operation_id,
        message=result.message,
        rationale=result.selected.rationale,
        proposed_operation_id=result.selected.proposed_operation_id,
        retrieved_operations=result.retrieved,
        execution=result.execution,
        processing_mode=mode,
    )
