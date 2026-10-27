"""Mock bank: an in-memory ledger behind bank2ai's standardized MCP surface.

``banking_agent.bank.server`` is intentionally *not* imported here — it is a
``python -m`` entry point, and re-exporting it would make Python warn about the
module being loaded twice.
"""

from .ledger import Ledger

__all__ = ["Ledger"]
