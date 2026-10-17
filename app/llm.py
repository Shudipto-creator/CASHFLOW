"""LLM provider abstraction for CASHFLOW.

Providers:
- mock: deterministic templates, no network. Used for demos and offline.
- bedrock: AWS Bedrock (existing provider).
- openai_compatible: any OpenAI-compatible endpoint via base_url/key/model from env.

The app must run fully, including the demo, with LLM_PROVIDER=mock and no cloud keys.
"""

import json
import logging
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

import httpx
from app.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)


class LLMError(Exception):
    pass


class LLMProvider(ABC):
    @abstractmethod
    def chat(self, messages: List[Dict[str, str]], temperature: float = 0.2, max_tokens: int = 1000) -> str:
        ...

    @abstractmethod
    def chat_json(self, messages: List[Dict[str, str]], schema: Dict[str, Any], temperature: float = 0.0, max_tokens: int = 1000) -> Dict[str, Any]:
        ...

    @abstractmethod
    def check_connection(self) -> bool:
        ...


class MockProvider(LLMProvider):
    """Deterministic templates. No network, no cloud keys."""

    def __init__(self, model: str = "mock-model") -> None:
        self.model = model
        self._budgets: Dict[str, int] = {}  # org_id -> remaining daily requests

    def chat(self, messages: List[Dict[str, str]], temperature: float = 0.2, max_tokens: int = 1000) -> str:
        user_text = ""
        for m in reversed(messages):
            if m.get("role") == "user":
                user_text = m.get("content", "")
                break
        return f"[mock] I received your question: '{user_text[:200]}'. In mock mode CASHFLOW uses deterministic calculations only. Connect a live LLM provider (bedrock or openai_compatible) for AI-generated answers."

    def chat_json(self, messages: List[Dict[str, str]], schema: Dict[str, Any], temperature: float = 0.0, max_tokens: int = 1000) -> Dict[str, Any]:
        user_text = ""
        for m in reversed(messages):
            if m.get("role") == "user":
                user_text = m.get("content", "")
                break
        return {
            "mock": True,
            "note": "deterministic template response",
            "received": user_text[:200],
        }

    def check_connection(self) -> bool:
        return True

    def budget_remaining(self, org_id: str) -> int:
        return self._budgets.get(org_id, settings.llm_daily_budget_per_org)

    def consume_budget(self, org_id: str) -> None:
        self._budgets[org_id] = max(0, self._budgets.get(org_id, settings.llm_daily_budget_per_org) - 1)


class BedrockProvider(LLMProvider):
    def __init__(self) -> None:
        try:
            import boto3  # type: ignore
        except ImportError as exc:
            raise LLMError("boto3 is required for the bedrock provider") from exc
        self.client = boto3.client(
            "bedrock-runtime",
            region_name=settings.aws_region if hasattr(settings, "aws_region") else "us-east-1",
        )
        self.model = settings.llm_model or "global.amazon.nova-2-lite-v1:0"

    def chat(self, messages: List[Dict[str, str]], temperature: float = 0.2, max_tokens: int = 1000) -> str:
        body = {
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        try:
            resp = self.client.invoke_model(
                modelId=self.model,
                body=json.dumps(body),
                contentType="application/json",
                accept="application/json",
            )
            result = json.loads(resp["body"].read())
            if "output" in result:
                return result["output"]["message"]["content"][0]["text"]
            return json.dumps(result)
        except Exception as exc:
            raise LLMError(f"Bedrock invocation failed: {exc}") from exc

    def chat_json(self, messages: List[Dict[str, str]], schema: Dict[str, Any], temperature: float = 0.0, max_tokens: int = 1000) -> Dict[str, Any]:
        text = self.chat(messages, temperature, max_tokens)
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            start = text.find("{")
            end = text.rfind("}")
            if start != -1 and end != -1 and end > start:
                return json.loads(text[start:end + 1])
            raise LLMError("Bedrock did not return valid JSON")

    def check_connection(self) -> bool:
        try:
            self.chat([{"role": "user", "content": "ping"}], max_tokens=5)
            return True
        except Exception:
            return False


class OpenAICompatibleProvider(LLMProvider):
    def __init__(self) -> None:
        self.base_url = settings.llm_base_url.rstrip("/")
        self.api_key = settings.llm_api_key
        self.model = settings.llm_model or "gpt-4o-mini"
        self.timeout = settings.llm_timeout_seconds

    def _headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def chat(self, messages: List[Dict[str, str]], temperature: float = 0.2, max_tokens: int = 1000) -> str:
        payload = {"model": self.model, "messages": messages, "temperature": temperature, "max_tokens": max_tokens}
        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.post(f"{self.base_url}/chat/completions", json=payload, headers=self._headers())
                resp.raise_for_status()
                data = resp.json()
                return data["choices"][0]["message"]["content"]
        except Exception as exc:
            raise LLMError(f"OpenAI-compatible invocation failed: {exc}") from exc

    def chat_json(self, messages: List[Dict[str, str]], schema: Dict[str, Any], temperature: float = 0.0, max_tokens: int = 1000) -> Dict[str, Any]:
        text = self.chat(messages, temperature, max_tokens)
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            start = text.find("{")
            end = text.rfind("}")
            if start != -1 and end != -1 and end > start:
                return json.loads(text[start:end + 1])
            raise LLMError("OpenAI-compatible did not return valid JSON")

    def check_connection(self) -> bool:
        try:
            self.chat([{"role": "user", "content": "ping"}], max_tokens=5)
            return True
        except Exception:
            return False


_PROVIDERS: Dict[str, LLMProvider] = {}


def get_llm_provider() -> LLMProvider:
    name = settings.llm_provider
    if name not in _PROVIDERS:
        if name == "mock":
            _PROVIDERS[name] = MockProvider(settings.llm_model)
        elif name == "bedrock":
            _PROVIDERS[name] = BedrockProvider()
        elif name == "openai_compatible":
            _PROVIDERS[name] = OpenAICompatibleProvider()
        else:
            raise LLMError(f"Unknown LLM provider: {name}")
    return _PROVIDERS[name]


class BudgetedLLM:
    """Wraps a provider with a per-organization daily request budget."""

    def __init__(self, provider: LLMProvider) -> None:
        self.provider = provider
        self._usage: Dict[str, int] = {}

    def chat(self, org_id: str, messages: List[Dict[str, str]], **kwargs) -> str:
        self._check_budget(org_id)
        try:
            text = self.provider.chat(messages, **kwargs)
        except Exception:
            self._usage[org_id] = self._usage.get(org_id, 0)
            raise
        self._usage[org_id] = self._usage.get(org_id, 0) + 1
        if isinstance(self.provider, MockProvider):
            self.provider.consume_budget(org_id)
        return text

    def chat_json(self, org_id: str, messages: List[Dict[str, str]], schema: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        self._check_budget(org_id)
        try:
            result = self.provider.chat_json(messages, schema, **kwargs)
        except Exception:
            raise
        self._usage[org_id] = self._usage.get(org_id, 0) + 1
        if isinstance(self.provider, MockProvider):
            self.provider.consume_budget(org_id)
        return result

    def _check_budget(self, org_id: str) -> None:
        used = self._usage.get(org_id, 0)
        limit = settings.llm_daily_budget_per_org
        if used >= limit:
            raise LLMError(f"LLM daily budget for organization {org_id} is exhausted")

    def check_connection(self) -> bool:
        return self.provider.check_connection()
