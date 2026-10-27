"""Runtime processing mode (aws | local) preference store."""

from __future__ import annotations

import json
import logging
import threading
from pathlib import Path
from typing import Literal

from app.config import get_settings

logger = logging.getLogger(__name__)

ProcessingMode = Literal["aws", "local"]
VALID_MODES = ("aws", "local")

_lock = threading.Lock()
_MODE_FILE = Path(__file__).resolve().parent.parent.parent / "data" / "processing_mode.json"


def _normalize_mode(mode: str | None) -> ProcessingMode:
    value = (mode or "").strip().lower()
    if value in VALID_MODES:
        return value  # type: ignore[return-value]
    return "aws"


def get_default_mode() -> ProcessingMode:
    settings = get_settings()
    return _normalize_mode(getattr(settings, "processing_mode", "aws"))


def get_processing_mode() -> ProcessingMode:
    """Return the active processing mode (file override → env default)."""
    with _lock:
        if _MODE_FILE.exists():
            try:
                data = json.loads(_MODE_FILE.read_text(encoding="utf-8"))
                return _normalize_mode(data.get("mode"))
            except Exception as exc:
                logger.warning("Failed to read processing mode file: %s", exc)
        return get_default_mode()


def set_processing_mode(mode: str) -> ProcessingMode:
    """Persist the active processing mode for subsequent requests."""
    normalized = _normalize_mode(mode)
    if mode and mode.strip().lower() not in VALID_MODES:
        raise ValueError(f"Invalid mode '{mode}'. Use 'aws' or 'local'.")

    with _lock:
        _MODE_FILE.parent.mkdir(parents=True, exist_ok=True)
        _MODE_FILE.write_text(
            json.dumps({"mode": normalized}, indent=2),
            encoding="utf-8",
        )
    logger.info("Processing mode set to: %s", normalized)
    return normalized


def resolve_mode(override: str | None = None) -> ProcessingMode:
    """Prefer an explicit per-request override, else the stored preference."""
    if override:
        return _normalize_mode(override)
    return get_processing_mode()
