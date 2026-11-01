"""Cryptographic proof of intent: Ed25519 signing, STID, and canonicalization.

Every banking request is signed end-to-end:

    Frontend (Ed25519 sign) -> Backend (verify + canonicalize + SHA-256 hash
                                 + re-sign for bank) -> Bank (verify signature)

The STID (Semantic Transaction ID) is a SHA-256 of ``method+path+body+client_id``,
giving a deterministic fingerprint of each transaction for duplicate detection.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping
from uuid import uuid4

from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from cryptography.exceptions import InvalidSignature


def compute_stid(
    method: str,
    path: str,
    body: Mapping[str, Any] | str,
    client_id: str,
) -> str:
    """Compute the Semantic Transaction ID.

    SHA-256 of ``method|path|canonical_body|client_id``. Deterministic so the
    same transaction always yields the same STID, enabling duplicate detection.
    """
    if isinstance(body, str):
        canonical_body = body
    else:
        canonical_body = json.dumps(body, sort_keys=True, separators=(",", ":"))
    payload = f"{method.upper()}|{path}|{canonical_body}|{client_id}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def canonicalize(payload: Mapping[str, Any]) -> str:
    """Canonicalize a JSON-serializable payload to a stable string.

    Keys are sorted recursively; separators are compact. The resulting string
    is what gets hashed and signed, so signature verification is deterministic.
    Pydantic models are converted to dicts via model_dump().
    """

    def _prepare(obj: Any) -> Any:
        if hasattr(obj, "model_dump"):
            return _prepare(obj.model_dump())
        if isinstance(obj, dict):
            return {k: _prepare(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [_prepare(v) for v in obj]
        return obj

    prepared = _prepare(payload)
    return json.dumps(prepared, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def hash_payload(canonical: str) -> str:
    """SHA-256 hex digest of a canonical payload string."""
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def sign_bytes(private_key: Ed25519PrivateKey, data: bytes) -> str:
    """Sign arbitrary bytes with Ed25519, returning Base64-encoded signature."""
    signature = private_key.sign(data)
    return __import__("base64").b64encode(signature).decode("ascii")


def verify_bytes(
    public_key: Ed25519PublicKey, data: bytes, signature_b64: str
) -> bool:
    """Verify an Ed25519 signature. Returns False on any failure."""
    import base64

    try:
        signature = base64.b64decode(signature_b64)
        public_key.verify(signature, data)
        return True
    except (InvalidSignature, Exception):
        return False


def sign_payload(
    private_key: Ed25519PrivateKey, payload: Mapping[str, Any]
) -> tuple[str, str]:
    """Sign a payload dict: returns (canonical_json, base64_signature)."""
    canonical = canonicalize(payload)
    signature = sign_bytes(private_key, canonical.encode("utf-8"))
    return canonical, signature


def verify_payload(
    public_key: Ed25519PublicKey, payload: Mapping[str, Any], signature_b64: str
) -> bool:
    """Verify a payload signature against its canonical form."""
    canonical = canonicalize(payload)
    return verify_bytes(public_key, canonical.encode("utf-8"), signature_b64)


def generate_client_id() -> str:
    """Generate a unique client id for STID binding."""
    return f"client_{uuid4().hex[:16]}"
