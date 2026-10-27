"""The transport seam: talk to the bank *only* through the okgate proxy.

The agent never gets a handle on the bank's MCP server. ``GateClient`` spawns
``okgate proxy`` as a child process, and okgate spawns the bank as *its*
upstream. Every tool call therefore passes the kill switch, scope checks,
classification, approvals, the loop breaker, the caps and the audit chain
before it can reach a handler — and the agent cannot bypass that by
construction, because it has no other route.

That single fact is the whole architecture. Keep it that way: if any code
anywhere opens a second connection to ``banking_agent.bank.server``, the gate
stops meaning anything.

okgate is distributed as an npm package and driven through ``npx``. The proxy
is started with its cwd set to the project root so the relative paths inside
``okgate.yaml`` resolve identically on every machine.
"""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import sys
from pathlib import Path
from typing import Any, Optional

from fastmcp import Client
from fastmcp.client.transports import StdioTransport

from .contract import GateCode, GateResult

#: okgate was renamed from agentguard; this is the npm package that ships it.
#: `@agentwares/okgate` is not published yet, so this is the only install path.
PACKAGE = "@agentwares/agentguard"


def _npx_argv() -> list[str]:
    """Resolve `npx` in a way that survives Windows' .cmd shim."""
    exe = shutil.which("npx")
    if exe is None:
        return ["npx"]
    if os.name == "nt" and exe.lower().endswith((".cmd", ".bat")):
        return ["cmd", "/c", exe]
    return [exe]


def _child_env() -> dict[str, str]:
    """Make the `python` in okgate.yaml resolve to *this* interpreter.

    okgate.yaml spells the bank's command as ``python``, which is what keeps the
    policy file portable across machines. The upstream still has to be the
    interpreter that has bank2ai installed, so that interpreter's own directory
    goes first on the child's PATH.
    """
    scripts = os.path.dirname(os.path.abspath(sys.executable))
    existing = os.environ.get("PATH", "")
    return {"PATH": os.pathsep.join([scripts, existing]) if existing else scripts}


def _text_of(result: Any) -> str:
    parts = []
    for block in getattr(result, "content", None) or []:
        text = getattr(block, "text", None)
        if text:
            parts.append(text)
    return "".join(parts)


def _parse_refusal(text: str) -> tuple[Optional[str], str, Optional[dict]]:
    """Pull (code, cause, details) out of an okgate error body."""
    try:
        payload = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return None, text.strip(), None
    if not isinstance(payload, dict):
        return None, text.strip(), None
    code = payload.get("code")
    cause = payload.get("cause") or payload.get("message") or text.strip()
    details = payload.get("details")
    return code, cause, details if isinstance(details, dict) else None


class GateClient:
    """A tool-calling session against a bank, gated by okgate."""

    def __init__(
        self,
        *,
        policy: Path,
        root: Path,
        run_id: str = "banking-agent",
        package: str = PACKAGE,
        npx: Optional[str] = None,
        timeout_s: float = 120.0,
    ) -> None:
        self.policy = Path(policy)
        self.root = Path(root)
        self.run_id = run_id
        self.package = package
        self.timeout_s = timeout_s
        self._npx = npx or _npx_argv()[0]
        self._npx_prefix = _npx_argv()[1:] if npx is None else []
        self._client: Optional[Client] = None

    # -- lifecycle ---------------------------------------------------------

    @property
    def state_dir(self) -> Path:
        return self.root / ".okgate"

    @property
    def audit_path(self) -> Path:
        return self.state_dir / "audit.jsonl"

    def _transport(self) -> StdioTransport:
        return StdioTransport(
            command=self._npx,
            args=[
                *self._npx_prefix,
                "-y",
                "-p",
                self.package,
                "okgate",
                "proxy",
                "--config",
                str(self.policy),
                "--run-id",
                self.run_id,
            ],
            cwd=str(self.root),
            env=_child_env(),
        )

    async def open(self) -> "GateClient":
        self._client = Client(self._transport(), timeout=self.timeout_s)
        await self._client.__aenter__()
        return self

    async def close(self) -> None:
        if self._client is not None:
            await self._client.__aexit__(None, None, None)
            self._client = None

    async def __aenter__(self) -> "GateClient":
        return await self.open()

    async def __aexit__(self, *exc: Any) -> None:
        await self.close()

    # -- tool calls --------------------------------------------------------

    async def tool_names(self) -> list[str]:
        """The tool surface the agent can see, as the proxy presents it."""
        assert self._client is not None, "GateClient is not open"
        tools = await self._client.list_tools()
        return sorted(t.name for t in tools)

    async def call(self, tool: str, args: Optional[dict[str, Any]] = None) -> GateResult:
        """Call one tool through the gate.

        Returns a :class:`GateResult`; never raises for a policy refusal or a
        business error, so callers have a single shape to branch on.
        """
        assert self._client is not None, "GateClient is not open"
        # A policy refusal is the expected answer for a gated call, not an
        # exceptional one, so ask FastMCP for the result instead of an
        # exception and let the caller branch on `code`.
        result = await self._client.call_tool(tool, dict(args or {}), raise_on_error=False)
        text = _text_of(result)

        if getattr(result, "is_error", False):
            code, cause, details = _parse_refusal(text)
            return GateResult(
                tool=tool,
                ok=False,
                code=code or GateCode.UPSTREAM_ERROR.value,
                message=cause,
                details=details,
            )

        value = getattr(result, "structured_content", None)
        if value is None and text.strip().startswith("{"):
            try:
                value = json.loads(text)
            except json.JSONDecodeError:
                value = None

        # The mock bank reports business failures inside an otherwise
        # successful response, e.g. {"code": "insufficient_funds", ...}.
        # `content` is bank2ai's human-readable line, when the response has one.
        business_code = value.get("code") if isinstance(value, dict) else None
        content = value.get("content") if isinstance(value, dict) else None
        return GateResult(
            tool=tool,
            ok=business_code is None,
            code=business_code,
            message=content or (text.strip() if value is None else ""),
            value=value if isinstance(value, dict) else None,
        )

    # -- administration (okgate's own CLI, not MCP) ------------------------

    async def _cli(self, *args: str) -> str:
        argv = [self._npx, *self._npx_prefix, "-y", "-p", self.package, "okgate", *args]
        proc = await asyncio.create_subprocess_exec(
            *argv,
            cwd=str(self.root),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        out, _ = await proc.communicate()
        return out.decode("utf-8", errors="replace").strip()

    async def kill(self, reason: str = "operator pressed the kill switch") -> str:
        """Halt every run. Backs the frontend Kill Switch button."""
        return await self._cli("kill", reason)

    async def resume(self) -> str:
        return await self._cli("resume")

    async def status(self) -> str:
        """Counters versus caps, kill state, and pending approvals."""
        return await self._cli("status")

    async def approve(self, approval_id: str) -> str:
        """Grant one pending approval. A human action, never an agent action."""
        return await self._cli("approve", approval_id)

    async def pending_approvals(self) -> str:
        return await self._cli("approvals")

    async def verify_audit(self, path: Optional[Path] = None) -> str:
        """Prove the hash-chained audit log was not edited."""
        target = Path(path) if path else self.audit_path
        return await self._cli("verify", str(target))

    async def read_audit(self) -> list[dict[str, Any]]:
        """The audit entries okgate has appended, oldest first."""
        if not self.audit_path.exists():
            return []
        rows = []
        for line in self.audit_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                rows.append(json.loads(line))
        return rows

    @staticmethod
    def approval_hint(approval_id: str) -> str:
        """The exact command a human runs to release a held call."""
        return f"npx -y -p {PACKAGE} okgate approve {approval_id}"


__all__ = ["GateClient", "GateResult", "PACKAGE"]
