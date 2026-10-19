"""Simple sklearn document-type classifier for No-AWS mode."""

from __future__ import annotations

import logging
import re
from typing import Dict, List, Optional, Tuple

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline

logger = logging.getLogger(__name__)

DOCUMENT_TYPES = [
    "bank_statement",
    "invoice",
    "profit_loss",
    "balance_sheet",
    "cash_flow_statement",
    "tax_document",
    "financial_document",
    "other",
]


def _training_corpus() -> Tuple[List[str], List[str]]:
    """Synthetic labeled samples for a lightweight offline classifier."""
    samples = [
        ("opening balance closing balance debit credit transaction nestatement", "bank_statement"),
        ("bank statement account number withdrawal deposit transfer neft rtgs", "bank_statement"),
        ("cheque clearance atm withdrawal available balance", "bank_statement"),
        ("invoice number bill to ship to quantity unit price subtotal due date", "invoice"),
        ("tax invoice gstin hsn code amount payable vendor customer", "invoice"),
        ("invoice total including tax payment terms", "invoice"),
        ("profit and loss statement revenue expenses net profit operating income", "profit_loss"),
        ("income statement cost of goods sold gross profit ebitda", "profit_loss"),
        ("p&l sales operating expenses net income", "profit_loss"),
        ("balance sheet assets liabilities equity current assets fixed assets", "balance_sheet"),
        ("total assets total liabilities shareholders equity retained earnings", "balance_sheet"),
        ("accounts receivable accounts payable inventory cash equivalents", "balance_sheet"),
        ("cash flow statement operating activities investing financing net cash", "cash_flow_statement"),
        ("cash from operations capex free cash flow beginning cash ending cash", "cash_flow_statement"),
        ("statement of cash flows burn rate runway", "cash_flow_statement"),
        ("gst return gstr income tax tds advance tax itr assessment year", "tax_document"),
        ("tax payment challan pan tan gst filing deadline", "tax_document"),
        ("form 26as tax deducted at source", "tax_document"),
        ("financial report summary metrics kpi dashboard overview", "financial_document"),
        ("monthly financial data revenue expenses liabilities loan emi", "financial_document"),
        ("company financial overview spreadsheet workbook sheets", "financial_document"),
        ("restaurant menu appetizers entrees beverages prices", "other"),
        ("resume curriculum vitae work experience education skills", "other"),
        ("rental agreement tenant landlord lease property terms", "other"),
        ("news article editorial headline reporter publication", "other"),
        ("product catalog item description sku specifications", "other"),
        ("meeting agenda attendees minutes action items", "other"),
        ("recipe ingredients cooking instructions servings", "other"),
        ("medical test results patient diagnosis treatment", "other"),
        ("school essay assignment course bibliography", "other"),
        ("travel itinerary flight hotel reservation confirmation", "other"),
        ("user manual installation instructions troubleshooting", "other"),
        ("event invitation date venue guest information", "other"),
    ]
    texts, labels = zip(*samples)
    return list(texts), list(labels)


class LocalDocumentClassifier:
    """TF-IDF + Logistic Regression document type classifier."""

    def __init__(self):
        self._pipeline: Optional[Pipeline] = None
        self._fit()

    def _fit(self) -> None:
        texts, labels = _training_corpus()
        self._pipeline = Pipeline(
            [
                (
                    "tfidf",
                    TfidfVectorizer(
                        lowercase=True,
                        ngram_range=(1, 2),
                        max_features=4000,
                        stop_words="english",
                    ),
                ),
                (
                    "clf",
                    LogisticRegression(
                        max_iter=500,
                        solver="lbfgs",
                    ),
                ),
            ]
        )
        self._pipeline.fit(texts, labels)
        logger.info("Local document classifier fitted on %s samples", len(texts))

    def classify(self, text: str, filename: str = "") -> Dict[str, object]:
        """
        Classify document text into a financial document type.

        Returns:
            {"document_type": str, "confidence": float, "scores": {type: float}}
        """
        blob = f"{filename}\n{text or ''}".strip()
        if not blob:
            return {
                "document_type": "financial_document",
                "confidence": 0.0,
                "scores": {},
            }

        # Keyword boost before ML for obvious headers
        boosted = self._keyword_boost(blob)
        if boosted:
            return boosted

        assert self._pipeline is not None
        proba = self._pipeline.predict_proba([blob[:20000]])[0]
        classes = list(self._pipeline.classes_)
        best_idx = int(np.argmax(proba))
        scores = {cls: float(proba[i]) for i, cls in enumerate(classes)}
        return {
            "document_type": classes[best_idx],
            "confidence": float(proba[best_idx]),
            "scores": scores,
        }

    def classify_many(self, texts: List[str], filenames: Optional[List[str]] = None) -> List[str]:
        filenames = filenames or [""] * len(texts)
        return [
            str(self.classify(text, filename).get("document_type", "financial_document"))
            for text, filename in zip(texts, filenames)
        ]

    @staticmethod
    def _keyword_boost(text: str) -> Optional[Dict[str, object]]:
        lowered = text.lower()
        patterns = [
            (r"\bbalance\s+sheet\b", "balance_sheet"),
            (r"\bprofit\s+and\s+loss\b|\bincome\s+statement\b|\bp\s*&\s*l\b", "profit_loss"),
            (r"\bcash\s+flow\s+statement\b|\bstatement\s+of\s+cash\s+flows\b", "cash_flow_statement"),
            (r"\bbank\s+statement\b|\baccount\s+statement\b", "bank_statement"),
            (r"\btax\s+invoice\b|\binvoice\s+no\b|\binvoice\s+number\b", "invoice"),
            (r"\bgstr\b|\bincome\s+tax\b|\btds\b|\bgst\s+return\b", "tax_document"),
        ]
        for pattern, label in patterns:
            if re.search(pattern, lowered):
                return {
                    "document_type": label,
                    "confidence": 0.92,
                    "scores": {label: 0.92},
                }
        return None
