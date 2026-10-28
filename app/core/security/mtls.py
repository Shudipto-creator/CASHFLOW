"""mTLS client certificate configuration for backend->bank channel.

Builds an ``ssl.SSLContext`` that presents a client certificate to the
okgate/bank upstream and verifies the server's certificate against a CA bundle.

Used by the backend when it opens the GateClient stdio transport to okgate.
"""

from __future__ import annotations

import ssl
from pathlib import Path
from typing import Optional

from app.config import get_settings


def build_client_ssl_context(
    cert_path: Optional[Path] = None,
    key_path: Optional[Path] = None,
    ca_path: Optional[Path] = None,
) -> Optional[ssl.SSLContext]:
    """Build an mTLS SSL context for outbound bank connections.

    Returns None if any path is missing (mTLS disabled, falls back to plain TLS).
    """
    settings = get_settings()
    cert = cert_path or Path(
        settings.bank_client_cert_path or ""
    ) if hasattr(settings, "bank_client_cert_path") else None
    key = key_path or Path(
        settings.bank_client_key_path or ""
    ) if hasattr(settings, "bank_client_key_path") else None
    ca = ca_path or Path(
        settings.bank_ca_cert_path or ""
    ) if hasattr(settings, "bank_ca_cert_path") else None

    if not (cert and key and ca):
        return None
    if not (cert.exists() and key.exists() and ca.exists()):
        return None

    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.load_cert_chain(str(cert), str(key))
    ctx.load_verify_locations(str(ca))
    ctx.verify_mode = ssl.CERT_REQUIRED
    ctx.check_hostname = True
    return ctx


def mTLS_headers(
    client_cert_path: Optional[Path] = None,
) -> dict[str, str]:
    """Return HTTP headers advertising mTLS client certificate fingerprint.

    Used as a hint for the bank/okgate side to correlate the cert with the
    authenticated client. The actual cert verification happens at the TLS layer.
    """
    headers: dict[str, str] = {}
    if client_cert_path and client_cert_path.exists():
        pem = client_cert_path.read_bytes()
        import hashlib

        fingerprint = hashlib.sha256(pem).hexdigest()[:16]
        headers["X-Client-Cert-Fingerprint"] = fingerprint
    return headers
