"""Wilson-inspired local ledger & billing engine.

Privacy-first: bank CSVs are categorized and analyzed locally in SQLite.
Inspired by openaccountant/wilson — 18 spending categories, anomaly detection
(duplicate charges, spending spikes, forgotten subscriptions).
"""

from app.services.wilson.engine import WilsonEngine

__all__ = ["WilsonEngine"]
