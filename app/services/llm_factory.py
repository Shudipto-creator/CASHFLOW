"""Factory for AWS Nova vs local/Ollama LLM clients."""

from __future__ import annotations

import logging
from typing import Any, Union

from app.services.mode_service import ProcessingMode, resolve_mode

logger = logging.getLogger(__name__)


def get_llm_client(mode: str | None = None) -> Any:
    """
    Return an LLM client for the requested processing mode.

    - aws   → NovaClient (Bedrock)
    - local → OllamaClient (chat/insights) — analysis uses LocalFinancialAnalyzer separately
    """
    resolved: ProcessingMode = resolve_mode(mode)
    if resolved == "local":
        from app.services.ollama_client import OllamaClient

        logger.info("Using OllamaClient (local mode)")
        return OllamaClient()

    from app.services.nova_client import NovaClient

    logger.info("Using NovaClient (aws mode)")
    return NovaClient()


def get_embedding_client(mode: str | None = None) -> Any:
    """Return embedding-capable client for the active mode."""
    resolved = resolve_mode(mode)
    if resolved == "local":
        from app.services.local_ml.embeddings import LocalEmbeddingClient

        return LocalEmbeddingClient()
    return get_llm_client("aws")


def get_mode_status() -> dict:
    """Health-ish status for both providers."""
    from app.services.mode_service import get_processing_mode

    active = get_processing_mode()
    status = {
        "active_mode": active,
        "modes": [
            {
                "id": "aws",
                "label": "AWS Mode",
                "description": "Amazon Bedrock Nova agents, Titan embeddings, Sonic TTS",
            },
            {
                "id": "local",
                "label": "Local Mode",
                "description": "Local sklearn classifier/analyzer + Ollama chat",
            },
        ],
        "aws": {"available": False},
        "local": {"available": False, "ollama": False},
    }

    try:
        from app.services.nova_client import NovaClient

        status["aws"]["available"] = NovaClient().check_connection()
    except Exception as exc:
        status["aws"]["error"] = str(exc)

    try:
        from app.services.ollama_client import OllamaClient

        ollama = OllamaClient()
        ollama_ok = ollama.check_connection()
        status["local"]["ollama"] = ollama_ok
        # Local analysis works even if Ollama is down (chat would fail)
        status["local"]["available"] = True
        status["local"]["chat_ready"] = ollama_ok
    except Exception as exc:
        status["local"]["error"] = str(exc)
        status["local"]["available"] = True  # ML analyzer still usable

    return status
