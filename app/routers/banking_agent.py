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
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app import models
from app.dependencies import get_current_user
from app.services.mode_service import resolve_mode
from app.services.llm_banking_agent import LLMBankingAgent, AgentResult

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/banking", tags=["banking-agent"])

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


def _get_agent(mode: str) -> LLMBankingAgent:
    agent = _AGENT_CACHE.get(mode)
    if agent is None:
        agent = LLMBankingAgent.build(
            policy=POLICY,
            root=GATE_ROOT,
            state_dir=STATE_DIR,
            persist_dir=VECTOR_STORE_DIR,
            subject="account-holder",
            run_id=f"llm-agent-{mode}",
            use_llm=True,
        )
        _AGENT_CACHE[mode] = agent
        logger.info("Built LLM banking agent (mode=%s)", mode)
    return agent


@router.post("/agent/chat", response_model=AgentChatResponse)
async def agent_chat(
    payload: AgentChatRequest,
    user: models.User = Depends(get_current_user),
):
    """Send a message to the LLM banking agent and get its action back."""
    mode = resolve_mode(payload.processing_mode)
    agent = _get_agent(mode)

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
