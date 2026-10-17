"""Orchestrate local classify + analyze pipeline (No-AWS)."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from app.services.local_ml.analyzer import LocalFinancialAnalyzer
from app.services.local_ml.classifier import LocalDocumentClassifier

logger = logging.getLogger(__name__)

_classifier: Optional[LocalDocumentClassifier] = None
_analyzer: Optional[LocalFinancialAnalyzer] = None


def _get_classifier() -> LocalDocumentClassifier:
    global _classifier
    if _classifier is None:
        _classifier = LocalDocumentClassifier()
    return _classifier


def _get_analyzer() -> LocalFinancialAnalyzer:
    global _analyzer
    if _analyzer is None:
        _analyzer = LocalFinancialAnalyzer()
    return _analyzer


def run_local_analysis(
    documents_text: str,
    document_types: Optional[List[str]] = None,
    filenames: Optional[List[str]] = None,
    text_chunks: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Run local ML classification + financial analysis.

    Returns a report_data dict compatible with the AWS agent pipeline output.
    """
    classifier = _get_classifier()
    analyzer = _get_analyzer()

    classified_types: List[str] = []
    classification_details: List[Dict[str, Any]] = []

    chunks = text_chunks or ([documents_text] if documents_text else [])
    names = filenames or [""] * len(chunks)

    for idx, chunk in enumerate(chunks):
        filename = names[idx] if idx < len(names) else ""
        result = classifier.classify(chunk, filename=filename)
        classified_types.append(str(result.get("document_type", "financial_document")))
        classification_details.append(result)

    # Prefer freshly classified types; fall back to caller-provided types
    final_types = classified_types or document_types or ["financial_document"]

    logger.info("Local analysis document types: %s", final_types)
    report = analyzer.analyze(documents_text, document_types=final_types)
    report["local_classification"] = classification_details
    return report
