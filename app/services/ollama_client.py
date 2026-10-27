"""Ollama LLM client with NovaClient-compatible interface."""

from __future__ import annotations

import json
import logging
import re
import time
from typing import Any, Dict, List, Optional

import requests

from app.config import get_settings
from app.services.local_ml.embeddings import LocalEmbeddingClient

logger = logging.getLogger(__name__)
settings = get_settings()


class OllamaClient:
    """
    Local LLM client via Ollama HTTP API.

    Exposes the same methods used by agents / ask-cfo / dashboard:
    - invoke_agent
    - generate_embeddings
    - check_connection
    - synthesize_speech_with_sonic (stub — browser TTS fallback)
    """

    def __init__(self):
        self.base_url = settings.ollama_base_url.rstrip("/")
        self.model_id = settings.ollama_model
        self.timeout = settings.request_timeout_seconds
        self._embedder = LocalEmbeddingClient()
        logger.info(
            "Ollama client initialized (base_url=%s, model=%s)",
            self.base_url,
            self.model_id,
        )

    @staticmethod
    def _parse_json_response(response_text: str) -> Optional[Dict[str, Any]]:
        """Reuse Nova-style JSON parsing for agent-shaped outputs."""
        text = (response_text or "").strip()
        if not text:
            return None

        candidates = [text]
        if "```" in text:
            parts = text.split("```")
            for idx in range(1, len(parts), 2):
                block = parts[idx].strip()
                if block.lower().startswith("json"):
                    block = block.split("\n", 1)[1].strip() if "\n" in block else ""
                if block:
                    candidates.append(block)

        first_brace = text.find("{")
        last_brace = text.rfind("}")
        if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
            candidates.append(text[first_brace : last_brace + 1])

        decoder = json.JSONDecoder()
        for candidate in candidates:
            raw = candidate.strip()
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, dict):
                    return parsed
            except json.JSONDecodeError:
                pass

            for idx, ch in enumerate(raw):
                if ch != "{":
                    continue
                try:
                    parsed, _ = decoder.raw_decode(raw[idx:])
                    if isinstance(parsed, dict):
                        return parsed
                except json.JSONDecodeError:
                    continue

            normalized = raw.replace("\u201c", '"').replace("\u201d", '"')
            normalized = re.sub(r",\s*([}\]])", r"\1", normalized)
            try:
                parsed = json.loads(normalized)
                if isinstance(parsed, dict):
                    return parsed
            except json.JSONDecodeError:
                continue
        return None

    def invoke_agent(
        self,
        prompt: str,
        system_prompt: str,
        temperature: float = 0.3,
        max_tokens: int = 2000,
        reasoning_effort: str = "medium",
    ) -> Dict[str, Any]:
        """Call Ollama /api/chat and return parsed JSON or raw text dict."""
        del reasoning_effort  # unused; kept for NovaClient signature parity

        payload = {
            "model": self.model_id,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
            "messages": [
                {"role": "system", "content": system_prompt or ""},
                {"role": "user", "content": prompt or ""},
            ],
        }

        for attempt in range(settings.max_retries):
            try:
                logger.info(
                    "Invoking Ollama model %s (attempt %s/%s)",
                    self.model_id,
                    attempt + 1,
                    settings.max_retries,
                )
                resp = requests.post(
                    f"{self.base_url}/api/chat",
                    json=payload,
                    timeout=max(self.timeout, 120),
                )
                if resp.status_code != 200:
                    raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:300]}")

                data = resp.json()
                response_text = (
                    data.get("message", {}).get("content")
                    or data.get("response")
                    or ""
                )
                if not response_text:
                    return {"error": "Ollama returned empty response"}

                parsed = self._parse_json_response(response_text)
                if parsed is not None:
                    return parsed
                return {"response": response_text, "raw_text": True}

            except Exception as exc:
                logger.error("Ollama invoke failed (attempt %s): %s", attempt + 1, exc)
                if attempt < settings.max_retries - 1:
                    time.sleep(2**attempt)
                    continue
                return {"error": f"Failed to invoke Ollama: {exc}"}

        return {"error": "Max retries exceeded"}

    def generate_embeddings(self, text: str) -> List[float]:
        return self._embedder.generate_embeddings(text)

    def check_connection(self) -> bool:
        try:
            resp = requests.get(f"{self.base_url}/api/tags", timeout=3)
            if resp.status_code != 200:
                return False
            models = [m.get("name", "") for m in resp.json().get("models", [])]
            # Connection OK even if preferred model not pulled yet
            if self.model_id and not any(self.model_id.split(":")[0] in m for m in models):
                logger.warning(
                    "Ollama is up but model '%s' may not be pulled. Available: %s",
                    self.model_id,
                    models[:8],
                )
            return True
        except Exception as exc:
            logger.warning("Ollama connection check failed: %s", exc)
            return False

    def synthesize_speech_with_sonic(
        self,
        text: str,
        voice_id: str = "Matthew",
        audio_format: str = "mp3",
    ) -> Dict[str, Any]:
        del text, voice_id, audio_format
        return {
            "error": "Nova Sonic TTS is unavailable in local/Ollama mode; use browser speech synthesis",
        }
