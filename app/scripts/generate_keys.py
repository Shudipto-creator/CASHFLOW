"""One-time setup script: generate an Ed25519 signing keypair and encrypt the
private key at rest.

Run exactly once on a clean deployment:

    python app/scripts/generate_keys.py

The encrypted private key is written to ``app/secrets/signing_key.enc`` and the
public key to ``app/secrets/signing_key.pub``. The passphrase must be set in
``app/.env`` as ``KEY_PASSPHRASE`` before running this script.

Never commit ``app/secrets/`` to version control (it is in .gitignore).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Make `app` importable when run from the repo root.
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.core.security.keys import generate_and_store_key, SECRETS_DIR  # noqa: E402


def main() -> None:
    passphrase = os.environ.get("KEY_PASSPHRASE")
    if not passphrase:
        print("ERROR: KEY_PASSPHRASE environment variable is required", file=sys.stderr)
        print(
            "Example: KEY_PASSPHRASE='my-long-random-passphrase' python app/scripts/generate_keys.py",
            file=sys.stderr,
        )
        sys.exit(1)

    enc_path = SECRETS_DIR / "signing_key.enc"
    pub_path = SECRETS_DIR / "signing_key.pub"

    if enc_path.exists() or pub_path.exists():
        print(
            f"ERROR: key files already exist in {SECRETS_DIR}. Remove them first if you want to regenerate.",
            file=sys.stderr,
        )
        sys.exit(1)

    pub_b64 = generate_and_store_key(passphrase)
    print(f"Generated Ed25519 keypair in {SECRETS_DIR}")
    print(f"  Private key (encrypted): signing_key.enc")
    print(f"  Public key:             signing_key.pub")
    print(f"  Public key (base64):    {pub_b64}")
    print()
    print("Add KEY_PASSPHRASE to app/.env and never commit app/secrets/ to git.")


if __name__ == "__main__":
    main()
