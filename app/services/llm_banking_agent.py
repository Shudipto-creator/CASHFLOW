"""LLM-driven banking agent — Scenario 1: "Smart Transfer".

This module is the *LLM host* for Track 2's Scenario 1. A user sends a plain
message to the agent ("transfer ¥600 to 李娜", "show my accounts", ...) and the
agent:

1. retrieves the candidate banking operations that are **registered and
   implemented** from a RAG index (``OperationRag``) so it stays in context of
   what the bank can actually do;
2. asks an LLM selector to map the message onto **one** of those candidates;
3. **hard-guards** the LLM's answer against the authoritative registry — if the
   LLM proposes anything that is not a registered, implemented operation, the
   agent refuses with a "not implemented" message and never fabricates a result;
4. executes the operation through the Zero-Trust banking gate
   (``banking_agent.gate.SecureBankGate``), never through a second connection.

The guard is the point of this module. The LLM is *free to propose* but not
*free to create*: execution is only ever dispatched by ``operation.id`` after a
dict-lookup against ``BANKING_OPERATIONS``. Anything else is reported as
``NOT_IMPLEMENTED`` and dropped.
"""

from __future__ import annotations

import json
import logging
import re
import shutil
import sys
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

#: The repo has two `banking_agent` packages: the top-level `banking_agent/`
#: (WeCom bot) and `banking-agent/banking_agent/` (the Zero-Trust gate). The
#: executor needs the gate one, so its directory must win on ``sys.path``.
_GATE_DIR = Path(__file__).resolve().parents[2] / "banking-agent"
if str(_GATE_DIR) not in sys.path:
    sys.path.insert(0, str(_GATE_DIR))

# ============================================================================
# 1. The authoritative registry of implemented banking operations
# ============================================================================
#
# This is the ONLY list of operations the agent may execute. It mirrors the
# surface that is actually wired up:
#   - the bank2ai MCP tools exposed through okgate (banking-agent/bank/server.py)
#   - the Zero-Trust tier rules (banking-agent/banking_agent/gate/tiers.py)
#   - the admin CLI on GateClient and the FX endpoints on the REST router.
#
# "implemented" here means: a handler exists and a call reaches it. Anything a
# user asks for that is NOT in this list is answered with a "not implemented"
# message — the agent never invents an operation.


@dataclass(frozen=True)
class BankingOperation:
    """One registered, implemented banking operation."""

    id: str                       # canonical id; the only key the executor accepts
    name: str                     # human-readable name
    kind: str                     # "read" | "transfer" | "confirm" | "admin" | "fx"
    summary: str                  # one-line description, embedded into RAG
    intent_hints: tuple[str, ...] # natural-language phrases that usually map here
    required_args: tuple[str, ...] = ()
    needs_mfa_tools: bool = False  # reserved for Track 2 tools that are NOT in bank2ai yet


#: Read-only tools — GREEN tier, execute automatically (tiers.GREEN_TOOLS).
_READ_OPS = (
    BankingOperation(
        id="get-accounts",
        name="List accounts",
        kind="read",
        summary=(
            "List the accounts you hold, optionally filtered by withdrawal "
            "eligibility, type, status or usage. Read-only, runs automatically."
        ),
        intent_hints=("my accounts", "account balance", "accounts", "余额", "账户"),
    ),
    BankingOperation(
        id="get-transactions",
        name="List transactions",
        kind="read",
        summary=(
            "List recent transactions, optionally filtered by date, category, "
            "account, amount range or free-text search. Read-only."
        ),
        intent_hints=("transactions", "history", "交易记录", "流水"),
    ),
    BankingOperation(
        id="get-transaction",
        name="Get one transaction",
        kind="read",
        summary="Fetch a single transaction by its id. Read-only.",
        intent_hints=("transaction detail", "一笔交易", "transaction"),
        required_args=("transaction_id",),
    ),
    BankingOperation(
        id="get-categories",
        name="List transaction categories",
        kind="read",
        summary="List the transaction categories the bank understands. Read-only.",
        intent_hints=("categories", "分类"),
    ),
    BankingOperation(
        id="get-transactions-summary",
        name="Transaction summary",
        kind="read",
        summary=(
            "Summarise transactions grouped by category or direction "
            "(income/expenses). Read-only."
        ),
        intent_hints=("spending by category", "summary", "开销汇总", "支出分析"),
    ),
    BankingOperation(
        id="get-recipients",
        name="Find recipients",
        kind="read",
        summary="Find saved payment recipients by name. Read-only.",
        intent_hints=("recipients", "payee", "收款人"),
    ),
)

#: Money-moving / write tools.
_WRITE_OPS = (
    BankingOperation(
        id="prepare-transfer",
        name="Prepare a transfer",
        kind="transfer",
        summary=(
            "Price and reserve a transfer to a creditor. Carries the amount; the "
            "daily cumulative total decides whether it is Yellow (needs your "
            "confirmation) or Red (needs strong SMS verification)."
        ),
        intent_hints=(
            "transfer", "send money", "pay", "转账", "汇款", "给", "pay someone",
        ),
        required_args=("debtor_account_id", "creditor", "amount", "currency"),
    ),
    BankingOperation(
        id="execute-transfer",
        name="Execute a prepared transfer",
        kind="confirm",
        summary=(
            "Settle a transfer intent that was already prepared. Irreversible; "
            "a human must confirm (and okgate may hold it for approval)."
        ),
        intent_hints=("settle transfer", "confirm transfer", "execute", "执行转账"),
        required_args=("transfer_intent_id",),
    ),
    BankingOperation(
        id="create-recipient",
        name="Create a recipient",
        kind="confirm",
        summary=(
            "Register a new payment recipient (name + account identifier). "
            "Irreversible; a human confirms the details first."
        ),
        intent_hints=("add recipient", "new payee", "添加收款人", "create recipient"),
        required_args=("name", "account_identifier"),
    ),
)

#: Administrative CLI operations (GateClient, admin-only in the REST layer).
_ADMIN_OPS = (
    BankingOperation(
        id="kill",
        name="Kill switch",
        kind="admin",
        summary="Halt every banking call, reads included. Operator/admin only.",
        intent_hints=("kill switch", "halt", "stop all", "停用", "kill"),
    ),
    BankingOperation(
        id="resume",
        name="Resume service",
        kind="admin",
        summary="Clear the kill switch and resume normal banking service. Admin only.",
        intent_hints=("resume", "restore", "恢复"),
    ),
)

#: FX operations — implemented on the REST router (banking.py), price via
#: exchangerate-api.com when EXCHANGERATE_API_KEY is configured.
_FX_OPS = (
    BankingOperation(
        id="fx/convert",
        name="Convert currency",
        kind="fx",
        summary=(
            "Convert an amount from one currency to another using live FX "
            "rates, applying a 1% conversion fee."
        ),
        intent_hints=("convert", "currency", "exchange", "汇率", "兑换"),
        required_args=("from_currency", "to_currency", "amount"),
    ),
    BankingOperation(
        id="fx/rates",
        name="Get exchange rate",
        kind="fx",
        summary="Look up the current exchange rate between two currencies.",
        intent_hints=("exchange rate", "fx rate", "汇率查询"),
        required_args=("from_currency", "to_currency"),
    ),
)

#: Full registry — one flat dict, keyed by operation id.
BANKING_OPERATIONS: dict[str, BankingOperation] = {
    op.id: op
    for op in (*_READ_OPS, *_WRITE_OPS, *_ADMIN_OPS, *_FX_OPS)
}

#: Human message shown when the requested operation is not implemented.
NOT_IMPLEMENTED_MESSAGE = (
    "That operation is not implemented yet — the agent can only use the banking "
    "operations that are registered and wired up. Available: "
    + ", ".join(sorted(BANKING_OPERATIONS))
    + "."
)

# ============================================================================
# 2. RAG over the operations catalog ("stay in context")
# ============================================================================
#
# The catalog is embedded into a dedicated ChromaDB collection so that, for any
# incoming message, we retrieve the operations that are *actually available* and
# only those are handed to the LLM. Chroma's default ONNX embedding function is
# used so retrieval works offline; a lexical fallback keeps the agent alive if
# the vector store is unavailable.


class OperationRag:
    """Retrieves registered operations relevant to a natural-language message."""

    def __init__(
        self,
        *,
        persist_dir: Optional[Path] = None,
        collection_name: str = "banking_operations",
        top_k: int = 6,
    ) -> None:
        self.persist_dir = persist_dir
        self.collection_name = collection_name
        self.top_k = top_k
        self._collection: Any = None

    # -- lifecycle -----------------------------------------------------------

    def build(self, force: bool = False) -> bool:
        """Seed the collection with the operations catalog (idempotent).

        Returns True if the collection is ready to query.
        """
        try:
            import chromadb

            client_kwargs: dict[str, Any] = {
                "settings": chromadb.config.Settings(anonymized_telemetry=False),
            }
            if self.persist_dir is not None:
                self.persist_dir.mkdir(parents=True, exist_ok=True)
                client_kwargs["path"] = str(self.persist_dir)

            client = chromadb.PersistentClient(**client_kwargs)
            collection = client.get_or_create_collection(self.collection_name)

            if force:
                existing = collection.get()["ids"]
                if existing:
                    collection.delete(existing)

            if not collection.get()["ids"]:
                ids = [op.id for op in BANKING_OPERATIONS.values()]
                documents = [
                    f"{op.name}. {op.summary}"
                    for op in BANKING_OPERATIONS.values()
                ]
                metadatas = [
                    {"operation_id": op.id, "kind": op.kind}
                    for op in BANKING_OPERATIONS.values()
                ]
                collection.add(ids=ids, documents=documents, metadatas=metadatas)

            self._collection = collection
            return True
        except Exception as exc:  # pragma: no cover - environment dependent
            logger.warning("OperationRag unavailable (%s); using lexical fallback", exc)
            self._collection = None
            return False

    def retrieve(self, message: str, top_k: Optional[int] = None) -> list[str]:
        """Return operation ids relevant to ``message``, most relevant first."""
        k = top_k or self.top_k
        if self._collection is not None:
            try:
                results = self._collection.query(
                    query_texts=[message],
                    n_results=min(k, len(BANKING_OPERATIONS)),
                )
                ids = results["ids"][0] if results and results.get("ids") else []
                return [str(i) for i in ids if i in BANKING_OPERATIONS]
            except Exception as exc:
                logger.warning("RAG query failed (%s); falling back to lexical", exc)
        return self._lexical(message, k)

    @staticmethod
    def _lexical(message: str, top_k: int) -> list[str]:
        """Deterministic keyword-overlap retrieval used when the store is down."""
        tokens = set(re.findall(r"[a-z0-9\u4e00-\u9fff]+", message.lower()))
        scored: list[tuple[float, str]] = []
        for op in BANKING_OPERATIONS.values():
            haystack = " ".join(
                (op.name, op.summary, " ".join(op.intent_hints))
            ).lower()
            hit = sum(1 for tok in tokens if tok in haystack)
            if hit:
                scored.append((hit, op.id))
        scored.sort(key=lambda pair: (-pair[0], pair[1]))
        return [op_id for _, op_id in scored[:top_k]]


# ============================================================================
# 3. Selectors — map a message to one candidate operation
# ============================================================================
#
# Two implementations share one contract. The LLM selector is the real one; the
# deterministic selector is a guaranteed-to-work fallback for offline runs and
# for environments without a reachable model. Both only ever pick from the
# candidate set / registry handed to them — they cannot create operations.


@dataclass
class SelectResult:
    """What a selector decided for one message."""

    operation_id: Optional[str] = None
    args: dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0
    rationale: str = ""
    proposed_by: str = "selector"
    not_implemented: bool = False
    proposed_operation_id: Optional[str] = None  # what the LLM said, before the guard


class DeterministicSelector:
    """Keyword-based resolver. Never invents operations; maps onto the registry."""

    #: Words that carry no signal and must not trigger a lexical match.
    STOPWORDS = frozenset(
        {
            "the", "a", "an", "of", "to", "and", "for", "with", "is", "are", "was",
            "my", "your", "me", "i", "we", "this", "that", "please", "want", "can",
            "do", "would", "could", "show", "see", "need", "get", "in", "on", "from",
            "it", "at", "by", "or", "as", "be", "not", "transfer", "转账", "给", "汇款",
        }
    )

    def __init__(self, registry: dict[str, BankingOperation] | None = None) -> None:
        self.registry = registry or BANKING_OPERATIONS

    @staticmethod
    def _meaningful_tokens(text: str) -> set[str]:
        return {
            t
            for t in re.findall(r"[a-z0-9\u4e00-\u9fff]+", text.lower())
            if t not in DeterministicSelector.STOPWORDS
        }

    def select(self, message: str, candidates: Optional[list[str]] = None) -> SelectResult:
        msg = message.lower()
        pool = (
            [self.registry[c] for c in candidates if c in self.registry]
            if candidates
            else list(self.registry.values())
        )
        tokens = self._meaningful_tokens(msg)

        # 1. A strong, explicit intent hint wins.
        for op in pool:
            if any(hint in msg for hint in op.intent_hints):
                args = _transfer_args(message) if op.id == "prepare-transfer" else {}
                return SelectResult(
                    operation_id=op.id,
                    args=args,
                    confidence=0.8,
                    rationale=f"matched intent hint of '{op.id}'",
                    proposed_by="deterministic",
                )

        # 2. Otherwise only take a candidate if it shares *meaningful* vocabulary
        #    with the message (stopwords excluded). No overlap => the message
        #    does not map onto any registered operation => NOT_IMPLEMENTED.
        for op in pool:
            haystack = self._meaningful_tokens(
                " ".join((op.name, op.summary, " ".join(op.intent_hints)))
            )
            shared = tokens & haystack
            if shared:
                args = _transfer_args(message) if op.id == "prepare-transfer" else {}
                return SelectResult(
                    operation_id=op.id,
                    args=args,
                    confidence=0.5,
                    rationale=f"lexical overlap {sorted(shared)} with '{op.id}'",
                    proposed_by="deterministic",
                )

        return SelectResult(
            operation_id=None,
            confidence=0.0,
            rationale="no registered operation matched the message",
            proposed_by="deterministic",
            not_implemented=True,
        )


def _transfer_args(message: str) -> dict[str, Any]:
    """Best-effort argument extraction for a natural-language transfer message.

    Handles forms like "transfer ¥600 to 李娜", "转 600 给 小明",
    "pay 1000 to supplier". Amount defaults to 0 only if none can be parsed; the
    bank will refuse a 0-amount transfer rather than move money by mistake.
    """
    amount_match = re.search(r"(?:¥|￥|rmb|元|usd|eur)\s*(\d+(?:\.\d+)?)", message, re.I)
    if not amount_match:
        amount_match = re.search(r"\b(\d+(?:\.\d+)?)\b", message)
    amount = float(amount_match.group(1)) if amount_match else 0.0

    name = ""
    for sep in (" to ", " 给 ", " 转给 ", "给 ", "转给 "):
        idx = message.lower().rfind(sep)
        if idx != -1:
            tail = message[idx + len(sep):].strip()
            name = re.split(r"[,，。!\?]|\s+(?:now|please|today)$", tail)[0].strip()
            if name:
                break

    args: dict[str, Any] = {
        "amount": amount,
        "currency": "CNY",
        "debtor_account_id": "acc_cmb_001",
    }
    if name:
        args["creditor_name"] = name
    return args


class LLMSelector:
    """Ask the configured LLM to pick one operation from the candidate list.

    The system prompt is deliberately adversarial to operation-hallucination:
    the model is told it may ONLY answer with an operation present in the list,
    that it must never invent an operation id, and that it should signal
    "not_implemented" when no candidate fits. The hard guard in
    :class:`LLMBankingAgent` runs *after* this regardless.
    """

    SELECTION_SYSTEM_PROMPT = (
        "You are the intent layer of a Zero-Trust banking agent. You are given a "
        "user message and a list of AVAILABLE banking operations. Your only job "
        "is to decide which ONE available operation the message asks for, and to "
        "extract the arguments for it.\n"
        "STRICT RULES:\n"
        "1. You MUST pick from the AVAILABLE_OPERATIONS list only. Never invent, "
        "guess, or rename an operation id.\n"
        "2. If no operation in the list fits the message, return "
        '{"operation_id": null, "not_implemented": true}.\n'
        "3. Reply with a single JSON object:\n"
        '{"operation_id": "<id>", "args": {...}, "rationale": "<short>"}\n'
        "4. Do not add commentary outside the JSON."
    )

    def __init__(
        self,
        llm_client: Any,
        registry: dict[str, BankingOperation] | None = None,
    ) -> None:
        self.llm_client = llm_client
        self.registry = registry or BANKING_OPERATIONS

    def select(self, message: str, candidates: Optional[list[str]] = None) -> SelectResult:
        pool = (
            [self.registry[c] for c in candidates if c in self.registry]
            if candidates
            else list(self.registry.values())
        )
        listing = "\n".join(
            f"- {op.id}: {op.name} — {op.summary} (args: "
            f"{', '.join(op.required_args) if op.required_args else 'none'})"
            for op in pool
        )
        prompt = (
            f"USER MESSAGE: {message}\n\n"
            f"AVAILABLE_OPERATIONS:\n{listing}\n\n"
            "Which operation_id, if any, does this message request? Reply in JSON."
        )
        try:
            raw = self.llm_client.invoke_agent(
                prompt=prompt,
                system_prompt=self.SELECTION_SYSTEM_PROMPT,
                temperature=0.0,
                max_tokens=600,
            )
        except Exception as exc:
            logger.warning("LLM selector failed (%s); falling back to deterministic", exc)
            return DeterministicSelector(self.registry).select(message, candidates)

        if isinstance(raw, dict) and "error" in raw:
            logger.warning("LLM selector returned error (%s); deterministic fallback", raw["error"])
            return DeterministicSelector(self.registry).select(message, candidates)

        text = raw.get("response") if isinstance(raw, dict) else str(raw)
        parsed = self._parse_json(text)
        if not isinstance(parsed, dict):
            return DeterministicSelector(self.registry).select(message, candidates)

        op_id = parsed.get("operation_id")
        if parsed.get("not_implemented") or not op_id or op_id not in self.registry:
            # The LLM either said "not implemented" or proposed an id that is
            # NOT registered. The guard would catch this anyway; we short-circuit
            # so the message is clean.
            return SelectResult(
                operation_id=None,
                confidence=0.0,
                rationale=str(parsed.get("rationale", "no registered operation fits")),
                proposed_by="llm",
                not_implemented=True,
                proposed_operation_id=op_id if isinstance(op_id, str) else None,
            )

        args = parsed.get("args")
        return SelectResult(
            operation_id=op_id,
            args=args if isinstance(args, dict) else {},
            confidence=1.0,
            rationale=str(parsed.get("rationale", "")),
            proposed_by="llm",
        )

    @staticmethod
    def _parse_json(text: str) -> Optional[dict[str, Any]]:
        """Parse JSON (incl. markdown-fenced) from an LLM reply."""
        if not text:
            return None
        cleaned = text.strip()
        # Extract first {...} block if prose surrounds it.
        start, end = cleaned.find("{"), cleaned.rfind("}")
        if start != -1 and end > start:
            cleaned = cleaned[start : end + 1]
        try:
            obj = json.loads(cleaned)
            return obj if isinstance(obj, dict) else None
        except json.JSONDecodeError:
            # Tolerate trailing commas and Python-style literals.
            cleaned = re.sub(r",\s*([}\]])", r"\1", cleaned)
            cleaned = re.sub(r"\bNone\b", "null", cleaned)
            cleaned = re.sub(r"\bTrue\b", "true", cleaned)
            cleaned = re.sub(r"\bFalse\b", "false", cleaned)
            try:
                obj = json.loads(cleaned)
                return obj if isinstance(obj, dict) else None
            except json.JSONDecodeError:
                return None


# ============================================================================
# 4. Executor — run an implemented operation through the Zero-Trust gate
# ============================================================================


class BankingExecutor:
    """Executes a registered operation via banking_agent.gate.SecureBankGate.

    Every call goes through the gate (the only route to the bank), preserving
    tier classification, MFA, confirmation, okgate caps/approvals and audit.
    """

    def __init__(
        self,
        *,
        policy: Path,
        root: Path,
        state_dir: Path,
        subject: str = "account-holder",
        run_id: str = "llm-agent",
    ) -> None:
        self.policy = policy
        self.root = root
        self.state_dir = state_dir
        self.subject = subject
        self.run_id = run_id

    def _mfa_verifier(self):
        from banking_agent.gate import SmsCodeMfa

        delivered: dict[str, str] = {}

        def deliver(subject: str, challenge_id: str, code: str) -> None:
            delivered[challenge_id] = code
            print(f"      [SMS to {subject}] verification code {code}")

        return SmsCodeMfa(deliver=deliver), delivered

    def _npx_for_gate(self) -> Optional[str]:
        """Return an npx path the gate can spawn on Windows.

        ``npx`` frequently lives under a path containing spaces (e.g. an
        AppData ``User Data\\...`` tree). The gate spawns it through ``cmd /c``,
        which splits such a path at the first space and aborts. Workaround: emit
        a space-free ``npx.cmd`` shim in the state dir and hand that to the gate.
        When npx is already space-free, ``None`` lets the gate resolve it itself.
        """
        npx = shutil.which("npx")
        if not npx or " " not in npx:
            return None
        shim_dir = None
        try:
            shim_dir = self.state_dir / "tools"
            shim_dir.mkdir(parents=True, exist_ok=True)
            shim = shim_dir / "npx.cmd"
            shim.write_text(f'@echo off\r\n"{npx}" %*\r\n', encoding="utf-8")
            return str(shim)
        except Exception as exc:  # pragma: no cover - env dependent
            logger.warning("could not build space-free npx shim (%s); gate may fail", exc)
            return None

    async def run(
        self,
        op: BankingOperation,
        args: dict[str, Any],
        *,
        confirmed: bool = False,
        mfa_challenge_id: Optional[str] = None,
        mfa_code: Optional[str] = None,
    ) -> dict[str, Any]:
        from banking_agent.gate import DailySpendLedger, GateClient, SecureBankGate

        client = GateClient(
            policy=self.policy,
            root=self.root,
            run_id=self.run_id,
            npx=self._npx_for_gate(),
        )
        await client.open()
        try:
            mfa, delivered = self._mfa_verifier()
            gate = SecureBankGate(
                client=client,
                spend=DailySpendLedger(self.state_dir / "daily_spend.json"),
                mfa=mfa,
                subject=self.subject,
            )

            if op.id == "prepare-transfer":
                outcome = await gate.transfer(
                    debtor_account_id=args.get("debtor_account_id", "acc_cmb_001"),
                    creditor=args.get("creditor", _default_creditor(args)),
                    amount=args.get("amount", 0),
                    currency=args.get("currency", "CNY"),
                    rail=args.get("rail", "swift"),
                    description=args.get("description"),
                    confirmed=confirmed,
                    mfa_challenge_id=mfa_challenge_id,
                    mfa_code=mfa_code,
                )
                return self._transfer_payload(outcome, delivered)
            if op.id == "execute-transfer":
                outcome = await gate.execute(args.get("transfer_intent_id", ""))
                return self._transfer_payload(outcome, delivered)

            outcome = await gate.call(op.id, args or None, confirmed=confirmed)
            return {
                "ok": outcome.ok,
                "code": outcome.code,
                "tier": outcome.tier.value if outcome.tier else None,
                "message": outcome.message,
                "value": outcome.value,
                "details": outcome.details or {},
            }
        finally:
            await client.close()

    @staticmethod
    def _transfer_payload(outcome: Any, delivered: dict[str, str]) -> dict[str, Any]:
        return {
            "ok": outcome.ok,
            "stage": outcome.stage,
            "code": _code_of(outcome),
            "tier": outcome.tier.value if outcome.tier else None,
            "intent_id": outcome.intent_id,
            "approval_id": outcome.approval_id,
            "approval_command": outcome.approval_command,
            "message": outcome.message,
            "needs_confirmation": outcome.needs_confirmation,
            "needs_mfa": outcome.needs_mfa,
            "needs_approval": outcome.needs_approval,
            "mfa_codes": delivered,
        }


def _code_of(outcome: Any) -> Optional[str]:
    step = getattr(outcome, "prepared") or getattr(outcome, "executed")
    return step.code if step and step.code else ("OK" if outcome.ok else None)


def _default_creditor(args: dict[str, Any]) -> dict[str, Any]:
    """Build a creditor from free-form args when the caller did not pass one."""
    name = args.get("creditor_name") or args.get("name") or "李娜"
    account = args.get("account_number") or "6225 8888 0000 1234"
    return {
        "name": name,
        "accountIdentifier": {
            "type": "accountNumber",
            "accountNumber": account,
            "country": args.get("country", "CN"),
        },
    }


# ============================================================================
# 5. The agent — retrieve → select → GUARD → execute
# ============================================================================


@dataclass
class AgentResult:
    """Structured outcome of one agent turn."""

    implemented: bool
    code: str                      # "OK" | "NOT_IMPLEMENTED" | gate code | "ERROR"
    operation_id: Optional[str]
    message: str                   # human-readable reply
    selected: SelectResult = field(default_factory=SelectResult)
    execution: Optional[dict[str, Any]] = None
    retrieved: list[str] = field(default_factory=list)


class LLMBankingAgent:
    """The smart-transfer scenario host."""

    def __init__(
        self,
        *,
        rag: Optional[OperationRag] = None,
        selector: Any = None,
        executor: BankingExecutor | None = None,
        registry: dict[str, BankingOperation] | None = None,
    ) -> None:
        self.registry = registry or BANKING_OPERATIONS
        self.rag = rag
        self.selector = selector
        self.executor = executor

    # -- construction helpers -----------------------------------------------

    @classmethod
    def build(
        cls,
        *,
        policy: Path,
        root: Path,
        state_dir: Path,
        persist_dir: Optional[Path] = None,
        subject: str = "account-holder",
        run_id: str = "llm-agent",
        use_llm: bool = True,
    ) -> "LLMBankingAgent":
        """Build a fully-wired agent.

        ``use_llm=True`` tries the configured LLM selector and falls back to the
        deterministic resolver when no model is reachable. The executor is always
        the Zero-Trust gate.
        """
        rag = OperationRag(persist_dir=persist_dir)
        rag.build()

        if use_llm:
            try:
                from app.services.llm_factory import get_llm_client

                selector: Any = LLMSelector(get_llm_client())
            except Exception as exc:  # pragma: no cover - env dependent
                logger.warning("LLM selector unavailable (%s); deterministic", exc)
                selector = DeterministicSelector()
        else:
            selector = DeterministicSelector()

        executor = BankingExecutor(
            policy=policy, root=root, state_dir=state_dir, subject=subject, run_id=run_id
        )
        return cls(rag=rag, selector=selector, executor=executor)

    # -- the turn ------------------------------------------------------------

    async def handle(
        self,
        message: str,
        *,
        confirmed: bool = False,
        mfa_challenge_id: Optional[str] = None,
        mfa_code: Optional[str] = None,
    ) -> AgentResult:
        """Process one user message end-to-end."""
        message = (message or "").strip()
        if not message:
            return AgentResult(
                implemented=False, code="ERROR", operation_id=None,
                message="Empty message. Tell the agent what you want to do.",
            )

        # 1. RAG — retrieve the operations that are actually available.
        retrieved = self.rag.retrieve(message) if self.rag else []
        retrieved = [oid for oid in retrieved if oid in self.registry]

        # 2. Select — map the message onto one candidate.
        selected = self.selector.select(message, retrieved or None)

        # 3. THE GUARD — never execute an operation the LLM invented.
        #    selected.operation_id is only ever a registry key (see selectors),
        #    but we re-check here because this is the security boundary.
        if selected.not_implemented or selected.operation_id is None:
            return AgentResult(
                implemented=False,
                code="NOT_IMPLEMENTED",
                operation_id=None,
                message=NOT_IMPLEMENTED_MESSAGE,
                selected=selected,
                retrieved=retrieved,
            )

        op = self.registry.get(selected.operation_id)
        if op is None:  # pragma: no cover - selectors already guard this
            return AgentResult(
                implemented=False,
                code="NOT_IMPLEMENTED",
                operation_id=selected.operation_id,
                message=NOT_IMPLEMENTED_MESSAGE,
                selected=selected,
                retrieved=retrieved,
            )

        # 4. Execute — only registered operations reach the executor.
        if self.executor is None:
            return AgentResult(
                implemented=True, code="ERROR", operation_id=op.id,
                message="Operation recognized but no executor is configured.",
                selected=selected, retrieved=retrieved,
            )

        try:
            execution = await self.executor.run(
                op,
                selected.args,
                confirmed=confirmed,
                mfa_challenge_id=mfa_challenge_id,
                mfa_code=mfa_code,
            )
        except Exception as exc:  # pragma: no cover - failure is reported, not raised
            logger.exception("Execution failed for %s", op.id)
            return AgentResult(
                implemented=True, code="ERROR", operation_id=op.id,
                message=f"Execution error: {exc}", selected=selected,
                execution={"ok": False, "error": str(exc)}, retrieved=retrieved,
            )

        code = execution.get("code") or ("OK" if execution.get("ok") else "ERROR")
        message_text = _render_execution(op, execution)
        return AgentResult(
            implemented=True,
            code=str(code),
            operation_id=op.id,
            message=message_text,
            selected=selected,
            execution=execution,
            retrieved=retrieved,
        )


def _render_execution(op: BankingOperation, execution: dict[str, Any]) -> str:
    """Human-friendly rendering of an executed operation's outcome."""
    if not execution.get("ok"):
        if execution.get("needs_confirmation"):
            return (
                f"{op.name}: awaiting your confirmation (Yellow tier). "
                f"Confirm to release the intent."
            )
        if execution.get("needs_mfa"):
            return (
                f"{op.name}: Red tier — strong SMS verification required. "
                f"Reply with the 6-digit code."
            )
        if execution.get("needs_approval"):
            return (
                f"{op.name}: held for human approval — run "
                f"{execution.get('approval_command')} to release it."
            )
        return f"{op.name} refused: {execution.get('message')}"

    if op.kind == "transfer":
        return (
            f"{op.name} prepared OK — intent {execution.get('intent_id')}, "
            f"tier {execution.get('tier')}."
        )
    if op.kind == "confirm":
        return f"{op.name} settled OK — intent {execution.get('intent_id')}."
    return f"{op.name} completed OK (tier {execution.get('tier')})."


__all__ = [
    "BANKING_OPERATIONS",
    "BankingOperation",
    "OperationRag",
    "DeterministicSelector",
    "LLMSelector",
    "BankingExecutor",
    "LLMBankingAgent",
    "AgentResult",
    "SelectResult",
    "NOT_IMPLEMENTED_MESSAGE",
]
