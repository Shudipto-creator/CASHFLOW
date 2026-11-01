"""AgentVault sandbox detection.

What AgentVault's `wrap` actually does — read this before making a claim about
it in the demo. Inspecting @inflectiv-ai/agentvault@1.0.1
(`dist/sandbox/runSandboxed.js`, `dist/sandbox/buildEnv.js`):

    const child = spawn(parts[0], parts.slice(1), { env, stdio: 'inherit', shell: true })

`wrap -p restrictive` builds a *filtered environment* and spawns the command with
it. `restrictive` passes through only PATH/HOME/USER/SHELL/TERM/LANG/LC_ALL/
TMPDIR/NODE_PATH plus whatever the profile rules allow, and injects
AGENTVAULT_SESSION / AGENTVAULT_PROFILE / AGENTVAULT_TRUST. There is no
namespace, proxy, firewall or seatbelt/firejail call anywhere in the package, and
the README describes itself as an encrypted credential vault.

So this proves **credential isolation** (a compromised agent process cannot read
secrets the profile denied), NOT network isolation. CASHFLOW's real network
control plane is okgate: the agent never holds a handle on the bank upstream, and
an unclassified tool hits `unknown: block`. Wrapping the backend in AgentVault is
a defence-in-depth layer on top of that, not a replacement for it — the health
endpoint and middleware below report exactly which layer is active so a judge can
tell the difference.
"""

from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)

# AGENTVAULT_SESSION/PROFILE/TRUST are what the CLI really injects. The bare
# SANDBOX_ID spelling is kept as an accepted alias for operators who set it by
# hand (e.g. docker-style wrappers).
SANDBOX_MARKER_VARS = (
    "AGENTVAULT_SESSION",
    "AGENTVAULT_PROFILE",
    "AGENTVAULT_TRUST",
    "AGENTVAULT_SANDBOX_ID",
)

OUTSIDE_SANDBOX_WARNING = (
    "Running outside AgentVault sandbox. Security isolation is not active."
)


def detect_sandbox(environ: dict[str, str] | None = None) -> dict[str, object]:
    """Describe the sandbox the process believes it is running inside."""
    env = environ if environ is not None else os.environ
    markers = {name: env[name] for name in SANDBOX_MARKER_VARS if env.get(name)}
    return {
        "active": bool(markers),
        "provider": "agentvault" if markers else "none",
        "profile": markers.get("AGENTVAULT_PROFILE"),
        "trust": markers.get("AGENTVAULT_TRUST"),
        "session": markers.get("AGENTVAULT_SESSION") or markers.get("AGENTVAULT_SANDBOX_ID"),
        "markers": sorted(markers),
    }


def log_startup_sandbox_state() -> dict[str, object]:
    """Emit the startup notice once instead of on every request."""
    state = detect_sandbox()
    if state["active"]:
        logger.info(
            "AgentVault sandbox detected (profile=%s, trust=%s, markers=%s). "
            "Credential isolation is active; note that AgentVault does not "
            "provide network isolation — okgate remains the enforcement point.",
            state["profile"],
            state["trust"],
            ",".join(state["markers"]),  # type: ignore[arg-type]
        )
    else:
        logger.warning(OUTSIDE_SANDBOX_WARNING)
    return state


async def sandbox_inspection_middleware(request, call_next):
    """Tag every request with the sandbox state and log the first one.

    Logging per-request would bury the backend log, so the middleware records
    state on `request.state`, echoes it as a response header for the frontend
    Security page, and logs once (at INFO) for the first request it sees. The
    startup event carries the recurring warning.
    """
    state = detect_sandbox()
    request.state.sandbox = state
    if not getattr(sandbox_inspection_middleware, "_logged_once", False):
        sandbox_inspection_middleware._logged_once = True
        logger.info(
            "sandbox inspection: %s (profile=%s)",
            state["provider"],
            state["profile"] or "n/a",
        )
    response = await call_next(request)
    response.headers["X-Sandbox"] = str(state["provider"])
    return response
