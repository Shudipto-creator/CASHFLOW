"""Ed25519 signing key management with encryption at rest.

The private key is generated once via ``generate_keys.py``, encrypted with
AES-256 (Fernet) using a passphrase from ``KEY_PASSPHRASE`` env var, and
stored on disk as ``secrets/signing_key.enc``. The FastAPI backend decrypts
it into memory at startup and holds it there for the lifetime of the process.

The plaintext key is NEVER written to disk. ``secrets/`` must be in .gitignore.
"""

from __future__ import annotations

import base64
import hashlib
import os
from pathlib import Path
from typing import Optional

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryption,
    PrivateFormat,
    PublicFormat,
    load_pem_private_key,
    load_pem_public_key,
)

#: Directory holding the encrypted key file (relative to app/).
SECRETS_DIR = Path(__file__).resolve().parents[3] / "app" / "secrets"
#: Encrypted private key file (created once by generate_keys.py).
ENC_KEY_PATH = SECRETS_DIR / "signing_key.enc"
#: Public key file (written alongside the encrypted private key).
PUB_KEY_PATH = SECRETS_DIR / "signing_key.pub"


def _fernet(passphrase: str) -> Fernet:
    """Derive a Fernet key from the passphrase using SHA-256."""
    key_material = base64.urlsafe_b64encode(hashlib.sha256(passphrase.encode()).digest())
    return Fernet(key_material)


def generate_and_store_key(passphrase: str, secrets_dir: Path = SECRETS_DIR) -> str:
    """Generate an Ed25519 keypair, encrypt the private key, and store both files.

    Returns the Base64-encoded public key.
    """
    secrets_dir.mkdir(parents=True, exist_ok=True)

    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key()

    private_pem = private_key.private_bytes(
        encoding=Encoding.PEM,
        format=PrivateFormat.PKCS8,
        encryption_algorithm=NoEncryption(),
    )
    public_pem = public_key.public_bytes(
        encoding=Encoding.PEM,
        format=PublicFormat.SubjectPublicKeyInfo,
    )

    fernet = _fernet(passphrase)
    encrypted = fernet.encrypt(private_pem)

    (secrets_dir / "signing_key.enc").write_bytes(encrypted)
    (secrets_dir / "signing_key.pub").write_bytes(public_pem)

    return base64.b64encode(public_pem).decode("ascii")


def load_private_key(passphrase: str, enc_path: Path = ENC_KEY_PATH) -> Ed25519PrivateKey:
    """Decrypt and load the Ed25519 private key into memory."""
    if not enc_path.exists():
        raise FileNotFoundError(
            f"Encrypted signing key not found at {enc_path}. "
            "Run generate_keys.py once to create it."
        )
    encrypted = enc_path.read_bytes()
    fernet = _fernet(passphrase)
    private_pem = fernet.decrypt(encrypted)
    return load_pem_private_key(private_pem, password=None)


def load_public_key(pub_path: Path = PUB_KEY_PATH) -> Ed25519PublicKey:
    """Load the Ed25519 public key from disk (for verification)."""
    public_pem = pub_path.read_bytes()
    return load_pem_public_key(public_pem)


def public_key_b64(pub_path: Path = PUB_KEY_PATH) -> str:
    """Return the Base64-encoded public key PEM."""
    return base64.b64encode(pub_path.read_bytes()).decode("ascii")
