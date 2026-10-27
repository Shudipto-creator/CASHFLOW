"""BillFlow-inspired local ledger & billing engine.

Privacy-first: bank CSVs are categorized and analyzed locally in SQLite.
Inspired by openaccountant/billflow — 18 spending categories, anomaly detection
(duplicate charges, spending spikes, forgotten subscriptions).
"""

from app.services.billflow.engine import BillFlowEngine

__all__ = ["BillFlowEngine"]
