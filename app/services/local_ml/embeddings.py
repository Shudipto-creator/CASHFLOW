"""Local embedding generator (no AWS) using hashing + optional Ollama."""

from __future__ import annotations

import hashlib
import logging
import math
import re
from typing import List, Optional

import numpy as np
import requests

from app.config import get_settings

logger = logging.getLogger(__name__)


class LocalEmbeddingClient:
    """
    Duck-typed embedding provider compatible with VectorStore.

    Prefer Ollama embeddings when available; otherwise use deterministic
    hashed bag-of-words vectors (fixed dimensionality).
    """

    def __init__(self, dimension: int = 384):
        settings = get_settings()
        self.dimension = dimension
        self.ollama_base_url = settings.ollama_base_url.rstrip("/")
        self.ollama_embed_model = settings.ollama_embed_model
        self._use_ollama = False
        self._probe_ollama()

    def _probe_ollama(self) -> None:
        try:
            resp = requests.get(f"{self.ollama_base_url}/api/tags", timeout=2)
            self._use_ollama = resp.status_code == 200
        except Exception:
            self._use_ollama = False

    def generate_embeddings(self, text: str) -> List[float]:
        if not text:
            return []

        if self._use_ollama:
            emb = self._ollama_embed(text)
            if emb:
                return emb

        return self._hash_embed(text)

    def check_connection(self) -> bool:
        try:
            return len(self.generate_embeddings("local embedding probe")) > 0
        except Exception:
            return False

    def invoke_agent(self, *args, **kwargs):
        raise NotImplementedError("LocalEmbeddingClient does not support LLM invocation")

    def synthesize_speech_with_sonic(self, *args, **kwargs):
        return {"error": "Speech synthesis is unavailable in local embedding mode"}

    def _ollama_embed(self, text: str) -> Optional[List[float]]:
        try:
            payload = {"model": self.ollama_embed_model, "prompt": text[:8000]}
            resp = requests.post(
                f"{self.ollama_base_url}/api/embeddings",
                json=payload,
                timeout=60,
            )
            if resp.status_code != 200:
                logger.warning("Ollama embeddings failed: %s", resp.text[:200])
                return None
            data = resp.json()
            embedding = data.get("embedding") or []
            if embedding:
                self.dimension = len(embedding)
            return [float(x) for x in embedding]
        except Exception as exc:
            logger.warning("Ollama embedding error: %s", exc)
            self._use_ollama = False
            return None

    def _hash_embed(self, text: str) -> List[float]:
        tokens = re.findall(r"[a-z0-9$%./-]+", text.lower())
        if not tokens:
            return [0.0] * self.dimension

        vec = np.zeros(self.dimension, dtype=np.float64)
        for token in tokens[:4000]:
            digest = hashlib.md5(token.encode("utf-8")).hexdigest()
            idx = int(digest[:8], 16) % self.dimension
            sign = 1.0 if int(digest[8:10], 16) % 2 == 0 else -1.0
            vec[idx] += sign

        norm = float(np.linalg.norm(vec))
        if norm > 0:
            vec = vec / norm
        else:
            # Avoid all-zero vectors for chroma
            vec[0] = 1.0 / math.sqrt(self.dimension)
        return vec.astype(float).tolist()
