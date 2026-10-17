"""App settings endpoints (processing mode switch)."""

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from typing import Literal, Optional

from app.services.mode_service import get_processing_mode, set_processing_mode
from app.services.llm_factory import get_mode_status

router = APIRouter(prefix="/api/settings", tags=["settings"])


class ModeUpdateRequest(BaseModel):
    mode: Literal["aws", "local"] = Field(..., description="Processing mode")


class ModeResponse(BaseModel):
    mode: str
    modes: list
    aws: dict
    local: dict
    active_mode: Optional[str] = None


@router.get("/mode", response_model=ModeResponse)
async def get_mode():
    """Get current processing mode and provider availability."""
    status_data = get_mode_status()
    return ModeResponse(
        mode=status_data["active_mode"],
        active_mode=status_data["active_mode"],
        modes=status_data["modes"],
        aws=status_data["aws"],
        local=status_data["local"],
    )


@router.put("/mode", response_model=ModeResponse)
async def update_mode(payload: ModeUpdateRequest):
    """Switch between AWS Bedrock and local (sklearn + Ollama) mode."""
    try:
        set_processing_mode(payload.mode)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    status_data = get_mode_status()
    return ModeResponse(
        mode=status_data["active_mode"],
        active_mode=status_data["active_mode"],
        modes=status_data["modes"],
        aws=status_data["aws"],
        local=status_data["local"],
    )
