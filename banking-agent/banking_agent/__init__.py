"""Track 2 — AI Agent for Banks: the security integration layer.

Three parts, deliberately separable so scenario owners can work in parallel:

``banking_agent.bank``
    A mock bank exposed through bank2ai's standardized MCP tool surface.
    Business-scenario owners add handlers here; the tool *names and schemas*
    come from bank2ai and must not be changed.

``banking_agent.gate``
    The Zero-Trust gate: the okgate policy proxy, the Green/Yellow/Red tier
    rules, MFA, and the CLI wrappers for the kill switch and audit checks.

``banking_agent.demo``
    End-to-end runs that print evidence for the deck and the security
    self-assessment.
"""

__all__ = ["bank", "gate"]
