"""Demo — Scenario 1: Smart Transfer through the LLM banking agent.

This script "sends messages to the agent" and shows, end to end, what the agent
does with each one:

  1. A *smart transfer* request ("transfer ¥600 to 李娜") is mapped onto the
     registered ``prepare-transfer`` operation (retrieved from the RAG index),
     run through the Zero-Trust gate, and — on confirmation — reserves an intent.
  2. A request for a capability that is NOT implemented ("change my password")
     is answered with a "not implemented" message.
  3. A hostile LLM that tries to *invent* an operation ("get-crypto-balance")
     is stopped by the hard registry guard — nothing is executed.

Run from the repo root with the banking-agent venv:

    cd CASHFLOW
    banking-agent\\.venv\\Scripts\\python.exe app\\scripts\\demo_smart_transfer.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from app.services.llm_banking_agent import (  # noqa: E402
    BANKING_OPERATIONS,
    LLMBankingAgent,
    LLMSelector,
    DeterministicSelector,
    OperationRag,
    BankingExecutor,
)


def section(title: str) -> None:
    print(f"\n{'=' * 72}\n{title}\n{'=' * 72}")


class HallucinatingLLM:
    """A deliberately-bad model that proposes an operation that does NOT exist.

    Used to prove the hard guard: the agent must refuse it with a "not
    implemented" message instead of executing (or inventing) anything.
    """

    def invoke_agent(self, *, prompt, system_prompt, temperature=0.0, max_tokens=600):
        return {
            "response": (
                '{"operation_id": "get-crypto-balance", '
                '"args": {"address": "0xabc"}, '
                '"rationale": "user asks to check crypto balance"}'
            )
        }


def working_policy() -> Path:
    """A generated copy of okgate.yaml whose upstream `python` is THIS venv's.

    okgate.yaml spells the upstream command as bare `python`, which on machines
    where `python` resolves to an interpreter *without* bank2ai (like this one)
    makes the proxy drop the connection. We never edit the trust-boundary
    okgate.yaml; instead we generate a working copy that points the upstream at
    the interpreter actually running this demo. The copy sits beside the real
    policy so its relative `cwd: .` paths still resolve.
    """
    gate_root = REPO_ROOT / "banking-agent"
    real = gate_root / "okgate.yaml"
    work = gate_root / "okgate.work.yaml"
    if not work.exists() or work.read_text(encoding="utf-8") != _patched(real):
        work.write_text(_patched(real), encoding="utf-8")
    return work


def _patched(real: Path) -> str:
    import sys

    text = real.read_text(encoding="utf-8")
    exe = sys.executable.replace("\\", "\\\\")
    return text.replace("command: python", f"command: \"{exe}\"")


async def run() -> None:
    policy = working_policy()  # real okgate.yaml stays untouched
    gate_root = REPO_ROOT / "banking-agent"
    state_dir = gate_root / ".state"
    rag_dir = REPO_ROOT / "data" / "vector_store"
    print(f"Policy for this run: {policy.name} (generated; real okgate.yaml untouched)")

    # ------------------------------------------------------------------ #
    print("CASHFLOW — Scenario 1: Smart Transfer (LLM banking agent)")
    print(f"Registered, implemented operations ({len(BANKING_OPERATIONS)}):")
    for op_id in sorted(BANKING_OPERATIONS):
        op = BANKING_OPERATIONS[op_id]
        print(f"  - {op_id:<26} [{op.kind:<8}] {op.name}")
    print("\nThe agent may ONLY execute these. Anything else => NOT_IMPLEMENTED.")

    # ------------------------------------------------------------------ #
    section("Build agent: RAG index (chromadb) + deterministic selector + gate")
    # Start from a clean daily ledger so a ¥600 transfer is Yellow, not Red.
    ledger_file = state_dir / "daily_spend.json"
    if ledger_file.exists():
        ledger_file.unlink()

    rag = OperationRag(persist_dir=rag_dir)
    seeded = rag.build(force=False)
    print(f"RAG ready: {seeded}  (seeded {len(BANKING_OPERATIONS)} operation docs)")

    executor = BankingExecutor(
        policy=policy, root=gate_root, state_dir=state_dir, subject="account-holder"
    )
    agent = LLMBankingAgent(rag=rag, selector=DeterministicSelector(), executor=executor)

    # ------------------------------------------------------------------ #
    section("STEP 1 — SMART TRANSFER: 'transfer ¥600 to 李娜'")
    msg = "transfer ¥600 to 李娜"
    retrieved = rag.retrieve(msg)
    print(f"RAG retrieved for '{msg}': {retrieved}")
    selected = agent.selector.select(msg, retrieved)
    print(f"Selector -> operation_id={selected.operation_id!r} (by {selected.proposed_by})")

    r1 = await agent.handle(msg)
    print(f"\n  implemented={r1.implemented}  code={r1.code}  op={r1.operation_id}")
    print(f"  message: {r1.message}")
    if r1.execution and r1.execution.get("needs_confirmation"):
        print("\n  The user confirms the Yellow-tier details; re-send the message...")
        r2 = await agent.handle(msg, confirmed=True)
        print(f"  implemented={r2.implemented}  code={r2.code}  op={r2.operation_id}")
        print(f"  message: {r2.message}")
        if r2.execution:
            print(f"  intent_id={r2.execution.get('intent_id')}  tier={r2.execution.get('tier')}")
            print(f"  daily spend now: {r2.execution.get('message', '')}")

    # ------------------------------------------------------------------ #
    section("STEP 2 — NOT IMPLEMENTED: 'change my password'")
    r3 = await agent.handle("change my password")
    print(f"  implemented={r3.implemented}  code={r3.code}  op={r3.operation_id}")
    print(f"  message: {r3.message}")

    # ------------------------------------------------------------------ #
    section("STEP 3 — GUARD TEST: a hostile LLM invents 'get-crypto-balance'")
    fake = LLMBankingAgent(rag=rag, selector=LLMSelector(HallucinatingLLM()), executor=None)
    r4 = await fake.handle("please check my crypto balance")
    print(f"  LLM proposed operation: {r4.selected.proposed_operation_id!r}")
    print(f"  implemented={r4.implemented}  code={r4.code}  op={r4.operation_id}")
    print(f"  message: {r4.message}")
    print(f"  -> the invented operation was NEVER executed (executor={None}).")

    # ------------------------------------------------------------------ #
    section("SUMMARY")
    passed = r1.implemented and r2.implemented and not r3.implemented and not r4.implemented
    print(f"  Smart transfer prepared:        {'PASS' if r1.implemented else 'FAIL'}")
    print(f"  Smart transfer confirmed:       {'PASS' if r2.implemented else 'FAIL'}")
    print(f"  Not-implemented op refused:     {'PASS' if not r3.implemented else 'FAIL'}")
    print(f"  LLM could NOT invent an op:     {'PASS' if not r4.implemented else 'FAIL'}")
    print(f"\n  OVERALL: {'ALL CHECKS PASSED' if passed else 'CHECK FAILED'}")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run()))
