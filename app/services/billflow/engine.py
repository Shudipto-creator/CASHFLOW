"""BillFlowEngine — local ledger facade (import, categorize, anomalies, summaries)."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Sequence

from sqlalchemy.orm import Session

from app import models
from app.services.billflow.anomalies import detect_anomalies, mark_recurring
from app.services.billflow.categorizer import categorize_description, categorize_transactions
from app.services.billflow.categories import BILLFLOW_CATEGORIES
from app.services.billflow.csv_importer import (
    deduplicate_transactions,
    parse_bank_csv,
)
from app.services.billflow.summaries import build_summary, money_gone_answer

logger = logging.getLogger(__name__)


class BillFlowEngine:
    """
    Privacy-first local bookkeeper inspired by openaccountant/billflow.

    All bank CSV processing, categorization, and anomaly math stay on-device
    in the application's SQLite database.
    """

    def __init__(self, db: Session, user_id: str):
        self.db = db
        self.user_id = user_id

    # ------------------------------------------------------------------
    # Import
    # ------------------------------------------------------------------

    def import_csv(
        self,
        content: bytes,
        filename: str = "",
        auto_categorize: bool = True,
    ) -> Dict[str, Any]:
        return self.import_document(content=content, filename=filename, auto_categorize=auto_categorize, dry_run=False)

    def import_document(
        self,
        content,
        filename="",
        file_path=None,
        auto_categorize=True,
        dry_run=False,
    ):
        import hashlib, os, tempfile
        from app.services.billflow.extractors import extract_transactions
        from app.services.local_ml.classifier import LocalDocumentClassifier

        ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        tmp = False
        if not file_path:
            fd, file_path = tempfile.mkstemp(suffix=ext or ".bin")
            os.close(fd)
            with open(file_path, "wb") as f:
                f.write(content)
            tmp = True
        try:
            txns, errors, bank = extract_transactions(ext, file_path, filename, content)
        except ValueError as exc:
            if tmp:
                try: os.remove(file_path)
                except OSError: pass
            raise
        try:
            text_for_classify = " ".join(t.get("description", "") for t in txns)
            clf = LocalDocumentClassifier()
            classification = clf.classify(text_for_classify or filename, filename)
        except Exception:
            classification = {"document_type": "financial_document", "confidence": 0.0}
        doc_type = str(classification.get("document_type", "financial_document"))
        confidence = float(classification.get("confidence", 0.0))
        file_hash = hashlib.sha256(content).hexdigest()
        existing_import = self.db.query(models.BillFlowImport).filter(models.BillFlowImport.user_id == self.user_id, models.BillFlowImport.file_hash == file_hash).first()
        if existing_import:
            if tmp:
                try: os.remove(file_path)
                except OSError: pass
            return {"status":"duplicate_file","message":"This file was already imported (SHA-256 match).","import_id":existing_import.import_id,"document_type":doc_type,"confidence":confidence,"bank":existing_import.bank,"filename":existing_import.filename,"transaction_count":existing_import.transaction_count,"inserted":0,"skipped_duplicates":0,"preview":txns[:5],"errors":errors,"privacy":"local_only"}
        if doc_type == "other" and not txns:
            if tmp:
                try: os.remove(file_path)
                except OSError: pass
            return {"status":"rejected","message":"Document classified as 'other' - not a transaction-bearing document.","document_type":doc_type,"confidence":confidence,"errors":errors,"privacy":"local_only"}
        if not txns:
            if tmp:
                try: os.remove(file_path)
                except OSError: pass
            return {"status":"no_transactions","message":"No transaction rows with parseable date/amount found.","document_type":doc_type,"confidence":confidence,"errors":errors,"privacy":"local_only"}
        existing_keys = {row.external_key for row in self.db.query(models.BillFlowTransaction.external_key).filter(models.BillFlowTransaction.user_id == self.user_id).all() if row.external_key}
        from app.services.billflow.categorizer import categorize_transactions
        from app.services.billflow.csv_importer import deduplicate_transactions
        fresh, skipped = deduplicate_transactions(txns, existing_keys)
        if auto_categorize and fresh:
            categorized, cat_stats = categorize_transactions(fresh)
            fresh = categorized
        else:
            cat_stats = {"total": len(fresh), "rule_matched": 0, "needing_review": 0}
        mark_recurring(fresh)
        preview = [{"date":t["date"],"description":t["description"],"amount":t["amount"],"category":t.get("category")} for t in fresh[:5]]
        if dry_run:
            if tmp:
                try: os.remove(file_path)
                except OSError: pass
            return {"status":"preview","document_type":doc_type,"confidence":confidence,"bank":bank,"filename":filename,"transaction_count":len(fresh),"inserted":0,"skipped_duplicates":skipped,"categorization":cat_stats,"preview":preview,"errors":errors,"privacy":"local_only"}
        import_row = models.BillFlowImport(user_id=self.user_id, filename=filename, file_hash=file_hash, bank=bank, transaction_count=len(fresh), date_range_start=min((t["date"] for t in fresh), default=None), date_range_end=max((t["date"] for t in fresh), default=None), import_metadata={"errors":errors,"categorization":cat_stats,"document_type":doc_type})
        self.db.add(import_row)
        self.db.flush()
        for txn in fresh:
            row = models.BillFlowTransaction(user_id=self.user_id, import_id=import_row.import_id, date=txn["date"], description=txn["description"], amount=float(txn["amount"]), category=txn.get("category"), category_confidence=txn.get("confidence"), categorization_method=txn.get("method"), bank=txn.get("bank") or bank, source_file=filename, external_key=txn.get("external_key"), is_recurring=bool(txn.get("is_recurring")), user_verified=False)
            self.db.add(row)
        self.db.commit()
        self.db.refresh(import_row)
        self._refresh_recurring_flags()
        if tmp:
            try: os.remove(file_path)
            except OSError: pass
        return {"status":"imported","import_id":import_row.import_id,"document_type":doc_type,"confidence":confidence,"bank":bank,"filename":filename,"file_hash":file_hash,"transaction_count":len(fresh),"inserted":len(fresh),"skipped_duplicates":skipped,"categorization":cat_stats,"preview":preview,"date_range_start":import_row.date_range_start,"date_range_end":import_row.date_range_end,"errors":errors,"privacy":"local_only"}
    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def list_transactions(
        self,
        *,
        category: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        search: Optional[str] = None,
        uncategorized_only: bool = False,
        limit: int = 100,
        offset: int = 0,
    ) -> Dict[str, Any]:
        q = self.db.query(models.BillFlowTransaction).filter(
            models.BillFlowTransaction.user_id == self.user_id
        )
        if category:
            q = q.filter(models.BillFlowTransaction.category == category)
        if start_date:
            q = q.filter(models.BillFlowTransaction.date >= start_date)
        if end_date:
            q = q.filter(models.BillFlowTransaction.date <= end_date)
        if uncategorized_only:
            q = q.filter(
                (models.BillFlowTransaction.category.is_(None))
                | (models.BillFlowTransaction.category == "Other")
            )
        if search:
            like = f"%{search}%"
            q = q.filter(models.BillFlowTransaction.description.ilike(like))

        total = q.count()
        rows = (
            q.order_by(models.BillFlowTransaction.date.desc(), models.BillFlowTransaction.id.desc())
            .offset(offset)
            .limit(min(limit, 500))
            .all()
        )
        return {
            "transactions": [self._txn_dict(r) for r in rows],
            "total": total,
            "limit": limit,
            "offset": offset,
        }

    def update_transaction(
        self,
        transaction_id: int,
        *,
        category: Optional[str] = None,
        user_verified: Optional[bool] = None,
        is_recurring: Optional[bool] = None,
    ) -> Dict[str, Any]:
        row = (
            self.db.query(models.BillFlowTransaction)
            .filter(
                models.BillFlowTransaction.id == transaction_id,
                models.BillFlowTransaction.user_id == self.user_id,
            )
            .first()
        )
        if not row:
            return {}

        if category is not None:
            if category not in BILLFLOW_CATEGORIES:
                raise ValueError(f"Invalid category. Must be one of: {BILLFLOW_CATEGORIES}")
            row.category = category
            row.categorization_method = "user"
            row.category_confidence = 1.0
            row.user_verified = True
        if user_verified is not None:
            row.user_verified = user_verified
        if is_recurring is not None:
            row.is_recurring = is_recurring

        self.db.commit()
        self.db.refresh(row)
        return self._txn_dict(row)

    def categorize_uncategorized(self) -> Dict[str, Any]:
        rows = (
            self.db.query(models.BillFlowTransaction)
            .filter(
                models.BillFlowTransaction.user_id == self.user_id,
                (models.BillFlowTransaction.category.is_(None))
                | (models.BillFlowTransaction.category == "Other")
                | (models.BillFlowTransaction.user_verified.is_(False)),
            )
            .all()
        )
        applied = 0
        needing_review = 0
        for row in rows:
            if row.user_verified:
                continue
            result = categorize_description(row.description, float(row.amount or 0))
            if result["category"] != (row.category or None) or row.category is None:
                row.category = result["category"]
                row.category_confidence = result["confidence"]
                row.categorization_method = result["method"]
                applied += 1
            if result["confidence"] < 0.7:
                needing_review += 1

        self.db.commit()
        self._refresh_recurring_flags()
        return {
            "scanned": len(rows),
            "updated": applied,
            "needing_review": needing_review,
            "categories": BILLFLOW_CATEGORIES,
            "privacy": "local_only",
        }

    def anomalies(self, types: Optional[List[str]] = None) -> Dict[str, Any]:
        txns = self._all_txn_dicts()
        return detect_anomalies(txns, types=types)

    def summary(
        self,
        *,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        group_by: str = "category",
    ) -> Dict[str, Any]:
        return build_summary(
            self._all_txn_dicts(),
            start_date=start_date,
            end_date=end_date,
            group_by=group_by,
        )

    def where_did_my_money_go(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> Dict[str, Any]:
        return money_gone_answer(
            self._all_txn_dicts(),
            start_date=start_date,
            end_date=end_date,
        )

    def overview(self) -> Dict[str, Any]:
        txns = self._all_txn_dicts()
        summary = build_summary(txns)
        anomalies = detect_anomalies(txns)
        imports = (
            self.db.query(models.BillFlowImport)
            .filter(models.BillFlowImport.user_id == self.user_id)
            .order_by(models.BillFlowImport.imported_at.desc())
            .limit(10)
            .all()
        )
        return {
            "totals": summary["totals"],
            "by_category": summary["by_category"][:8],
            "anomaly_summary": anomalies["summary"],
            "top_anomalies": (
                anomalies["duplicates"][:3]
                + anomalies["spikes"][:2]
                + anomalies["forgotten_subscriptions"][:3]
            ),
            "imports": [
                {
                    "import_id": i.import_id,
                    "filename": i.filename,
                    "bank": i.bank,
                    "transaction_count": i.transaction_count,
                    "imported_at": i.imported_at.isoformat() if i.imported_at else None,
                }
                for i in imports
            ],
            "categories": BILLFLOW_CATEGORIES,
            "privacy": "local_only",
            "answer_text": summary.get("answer_text"),
        }

    def context_for_ask_cfo(self) -> Optional[str]:
        """Compact local ledger context for AgentCFO prompts."""
        count = (
            self.db.query(models.BillFlowTransaction)
            .filter(models.BillFlowTransaction.user_id == self.user_id)
            .count()
        )
        if count == 0:
            return None

        summary = self.summary()
        anomalies = self.anomalies()
        lines = [
            "BILLFLOW LOCAL LEDGER (privacy-first, computed on-device):",
            "=" * 70,
            summary.get("answer_text") or "",
            f"Transactions stored locally: {count}",
            f"Spending: ${summary['totals']['spending']:,.2f} | Income: ${summary['totals']['income']:,.2f}",
            "",
            "Top categories:",
        ]
        for row in summary.get("by_category", [])[:5]:
            lines.append(
                f"  • {row['category']}: ${row['total']:,.2f} ({row['share_pct']}%)"
            )
        flags = anomalies.get("summary", {})
        lines.extend(
            [
                "",
                "Anomaly scan:",
                f"  • Duplicates: {flags.get('duplicate_count', 0)}",
                f"  • Spikes: {flags.get('spike_count', 0)}",
                f"  • Forgotten subscriptions: {flags.get('forgotten_subscription_count', 0)}",
                f"  • Potential annual savings: ${flags.get('potential_annual_savings', 0):,.2f}",
            ]
        )
        for finding in (
            anomalies.get("forgotten_subscriptions", [])[:3]
            + anomalies.get("duplicates", [])[:2]
        ):
            lines.append(f"  • [{finding.get('type')}] {finding.get('reason')}")
        lines.append("")
        lines.append(
            "When the CEO asks where money went, billing, subscriptions, or duplicate charges, "
            "prefer these BillFlow figures over estimates."
        )
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _all_txn_dicts(self) -> List[Dict[str, Any]]:
        rows = (
            self.db.query(models.BillFlowTransaction)
            .filter(models.BillFlowTransaction.user_id == self.user_id)
            .order_by(models.BillFlowTransaction.date.asc())
            .all()
        )
        return [self._txn_dict(r) for r in rows]

    @staticmethod
    def _txn_dict(row: models.BillFlowTransaction) -> Dict[str, Any]:
        return {
            "id": row.id,
            "date": row.date,
            "description": row.description,
            "amount": float(row.amount),
            "category": row.category,
            "confidence": row.category_confidence,
            "method": row.categorization_method,
            "bank": row.bank,
            "source_file": row.source_file,
            "external_key": row.external_key,
            "is_recurring": bool(row.is_recurring),
            "user_verified": bool(row.user_verified),
            "import_id": row.import_id,
        }

    def _refresh_recurring_flags(self) -> None:
        txns = self._all_txn_dicts()
        marked = mark_recurring(txns)
        recurring_ids = {t["id"] for t in marked if t.get("is_recurring") and t.get("id")}
        if not recurring_ids:
            return
        (
            self.db.query(models.BillFlowTransaction)
            .filter(
                models.BillFlowTransaction.user_id == self.user_id,
                models.BillFlowTransaction.id.in_(recurring_ids),
            )
            .update({models.BillFlowTransaction.is_recurring: True}, synchronize_session=False)
        )
        self.db.commit()
