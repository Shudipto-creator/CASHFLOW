"""Ask CASHFLOW endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List

from app.database import get_db
from app import models
from app.dependencies import get_current_user

router = APIRouter(tags=["ask"])


class AskRequest(BaseModel):
    question: str
    thread_id: Optional[str] = None
    mask: bool = True


class AskResponse(BaseModel):
    answer: str
    thread_id: str
    sources: List[dict] = []
    disclaimer: str = "Estimates based on your data. Not financial advice."


@router.post("/api/ask", response_model=AskResponse)
def ask_question(
    data: AskRequest,
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from app.security import mask_text
    from app.llm import get_llm_provider, BudgetedLLM

    if data.thread_id:
        thread = (
            db.query(models.ChatThread)
            .filter(models.ChatThread.id == data.thread_id, models.ChatThread.org_id == user.organization_id)
            .first()
        )
    else:
        thread = models.ChatThread(
            org_id=user.organization_id, user_id=user.id, title=data.question[:60]
        )
        db.add(thread)
        db.commit()
        db.refresh(thread)

    question = mask_text(data.question) if data.mask else data.question

    provider = BudgetedLLM(get_llm_provider())
    import os

    org_id = user.organization_id or ""
    try:
        answer = provider.chat(org_id, [{"role": "user", "content": question}])
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=f"AI service unavailable: {exc}")

    msg_user = models.ChatMessage(thread_id=thread.id, role="user", content=data.question)
    msg_a = models.ChatMessage(thread_id=thread.id, role="assistant", content=answer)
    db.add(msg_user)
    db.add(msg_a)
    db.commit()

    # call the LLM provider by name stored in settings (used elsewhere)
    from app.config import get_settings

    return AskResponse(answer=answer, thread_id=thread.id, sources=[])
