"""mTLS client certificate configuration for backend->bank channel.

Builds an ``ssl.SSLContext`` that presents a client certificate to the
okgate/bank upstream and verifies the server's certificate against a CA bundle.

Used by the backend when it opens the GateClient stdio transport to okgate.

Also provides an httpx.AsyncClient configured with client certificate for
forwarding calls to okgate via HTTP when the stdio transport is not used.
"""

from __future__ import annotations

import logging
import ssl
from pathlib import Path
from typing import Optional

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)


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


def build_mtls_client(
    cert_path: Optional[Path] = None,
    key_path: Optional[Path] = None,
    ca_path: Optional[Path] = None,
) -> Optional[httpx.AsyncClient]:
    """Build an httpx.AsyncClient configured with mTLS client certificate.

    Returns None if any path is missing (mTLS disabled).
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
        logger.warning(
            "mTLS client cert paths not configured. mTLS will not be used for "
            "backend->bank calls. Set BANK_CLIENT_CERT_PATH, BANK_CLIENT_KEY_PATH, "
            "and BANK_CA_CERT_PATH in .env to enable."
        )
        return None

    if not (cert.exists() and key.exists() and ca.exists()):
        logger.warning(
            "mTLS cert files not found at configured paths. mTLS disabled."
        )
        return None

    try:
        transport = httpx.AsyncHTTPTransport(
            cert=str(cert),
            verify=str(ca),
        )
        return httpx.AsyncClient(transport=transport)
    except Exception as exc:
        logger.warning(
            f"Failed to build mTLS client: {exc}. mTLS disabled."
        )
        return None


def check_mtls_readiness() -> bool:
    """Check if mTLS is properly configured for the backend->bank channel.

    Returns True if mTLS is configured, False otherwise.
    """
    settings = get_settings()
    cert_path = Path(
        settings.bank_client_cert_path or ""
    ) if hasattr(settings, "bank_client_cert_path") else None
    key_path = Path(
        settings.bank_client_key_path or ""
    ) if hasattr(settings, "bank_client_key_path") else None
    ca_path = Path(
        settings.bank_ca_cert_path or ""
    ) if hasattr(settings, "bank_ca_cert_path") else None

    if not (cert_path and key_path and ca_path):
        return False
    return cert_path.exists() and key_path.exists() and ca_path.exists()


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