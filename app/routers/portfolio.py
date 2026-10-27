"""TrueWealth-inspired portfolio analytics API (Mejbah & ROY)."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.dependencies import get_current_user
from app import models
from app.services.portfolio import PortfolioAnalyzer

router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])


class HoldingInput(BaseModel):
    symbol: str
    shares: float = Field(..., gt=0)
    price: Optional[float] = Field(None, gt=0)


class PortfolioAnalyzeRequest(BaseModel):
    holdings: Optional[List[HoldingInput]] = None
    text: Optional[str] = None
    history_period: str = "6mo"


@router.post("/analyze")
async def analyze_portfolio(
    body: PortfolioAnalyzeRequest,
    current_user: models.User = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Compute real portfolio risk metrics (allocation, vol, max drawdown).

    LLM callers should explain these numbers — not invent them.
    """
    analyzer = PortfolioAnalyzer()
    if body.holdings:
        holdings = [h.model_dump() for h in body.holdings]
        return analyzer.analyze(holdings, history_period=body.history_period)
    if body.text:
        return analyzer.analyze_from_text(body.text, history_period=body.history_period)
    return {
        "status": "empty",
        "message": "Provide holdings[] or a text description like '10 shares of AAPL'",
        "metrics": {},
        "positions": [],
    }
