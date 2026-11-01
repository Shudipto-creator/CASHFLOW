#!/usr/bin/env bash
# Run the CASHFLOW backend inside AgentVault's `restrictive` profile.
#
# WHAT THIS PROVES, AND WHAT IT DOES NOT
# --------------------------------------
# Verified against @inflectiv-ai/agentvault@1.0.1 (dist/sandbox/runSandboxed.js,
# dist/sandbox/buildEnv.js): `wrap` builds a filtered environment and does
#   spawn(command, args, { env, stdio: 'inherit', shell: true })
# `restrictive` = "deny everything except system vars", i.e. only
# PATH/HOME/USER/SHELL/TERM/LANG/LC_ALL/TMPDIR/NODE_PATH pass through, plus the
# vault secrets the profile allows, plus AGENTVAULT_SESSION/PROFILE/TRUST.
#
# So this is CREDENTIAL isolation: the wrapped process cannot read env secrets
# the profile denied. The package contains no namespace, firewall, proxy or
# seatbelt/firejail call, so it is NOT network isolation and it does not stop a
# compromised process from opening its own socket. In CASHFLOW the network and
# money-movement control plane is okgate (tier classification, ¥5,000/day cap,
# loop breaker, kill switch, `unknown: block`), and the wrapped backend still has
# to go through it. Keep the claim in the demo honest.
#
# Usage:
#   scripts/run_in_agentvault.sh                 # restrictive (default)
#   scripts/run_in_agentvault.sh moderate        # compare profiles
set -euo pipefail

PROFILE="${1:-restrictive}"
HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-8000}"
APP_MODULE="${APP_MODULE:-app.main:app}"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

say() { printf '\n\033[1;36m[agentvault]\033[0m %s\n' "$*"; }
die() { printf '\n\033[1;31m[agentvault]\033[0m %s\n' "$*" >&2; exit 1; }

# 1 — CLI present? We do not install global npm packages silently: it changes
# machine-wide state and runs third-party post-install code.
command -v agentvault >/dev/null 2>&1 \
  || die "agentvault not on PATH. Install it with: npm install -g @inflectiv-ai/agentvault"

say "agentvault: $(agentvault --version 2>/dev/null || echo unknown)  profile: $PROFILE"

# 2 — vault initialised? `wrap` loads .agentvault/profiles/<name>.yml and throws
# "Profile not found" otherwise.
if [ ! -d ".agentvault" ]; then
  say "no .agentvault directory — running 'agentvault init' (creates a passphrase-protected vault)"
  agentvault init
fi

if [ ! -f ".agentvault/profiles/${PROFILE}.yml" ]; then
  say "profile '${PROFILE}.yml' missing. Built-ins are restrictive / moderate / permissive."
  say "create it with: agentvault profile create ${PROFILE}"
  agentvault profile list || true
  exit 1
fi

# 3 — CASHFLOW's own secrets live in app/.env, which pydantic-settings +
# python-dotenv load from DISK inside the process. AgentVault only filters the
# parent environment, so .env still wins and the sandbox proves nothing about
# those values. To make the credential-isolation claim real, mirror the secrets
# into the vault and let the profile deny/allow them explicitly.
#
# Opt-in and use with care: `agentvault secret add KEY VALUE` passes the value in
# argv, which is readable from another account's process list on a shared machine.
# On a shared box, paste each value through the prompt instead of running this.
if [ -f "app/.env" ] && [ "${MIRROR_DOTENV_TO_VAULT:-0}" = "1" ]; then
  say "mirroring app/.env keys into the vault (set MIRROR_DOTENV_TO_VAULT=1 to enable)"
  while IFS='=' read -r key value; do
    case "$key" in
      ''|\#*) continue ;;
    esac
    agentvault secret add "$key" "$value" >/dev/null 2>&1 || \
      say "  skipped $key (already present or rejected by the vault)"
  done < <(grep -E '^[A-Z0-9_]+=' app/.env || true)
fi

# 4 — what the wrapped process will actually see. `preview` is the dry-run that
# answers "would this secret be allowed, redacted or denied" without launching.
say "profile preview (what the backend can read):"
agentvault preview -p "$PROFILE" || true

# 5 — launch. `wrap` splits the command on spaces, so no embedded quotes here.
say "wrapping: python -m uvicorn ${APP_MODULE} --host ${HOST} --port ${PORT}"
exec agentvault wrap -p "$PROFILE" \
  "python -m uvicorn ${APP_MODULE} --host ${HOST} --port ${PORT}"
