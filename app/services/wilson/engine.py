"""WilsonEngine — local ledger facade (import, categorize, anomalies, summaries)."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Sequence

from sqlalchemy.orm import Session

from app import models
from app.services.wilson.anomalies import detect_anomalies, mark_recurring
from app.services.wilson.categorizer import categorize_description, categorize_transactions
from app.services.wilson.categories import WILSON_CATEGORIES
from app.services.wilson.csv_importer import (
    deduplicate_transactions,
    parse_bank_csv,
)
from app.services.wilson.summaries import build_summary, money_gone_answer

logger = logging.getLogger(__name__)


class WilsonEngine:
    """
    Privacy-first local bookkeeper inspired by openaccountant/wilson.

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
        filename: str,
        auto_categorize: bool = True,
    ) -> Dict[str, Any]:
        """Parse a bank CSV, dedupe by file hash + external_key, persist rows."""
        parsed = parse_bank_csv(content, filename=filename)
        file_hash = parsed["file_hash"]

        existing_import = (
            self.db.query(models.WilsonImport)
            .filter(
                models.WilsonImport.user_id == self.user_id,
                models.WilsonImport.file_hash == file_hash,
            )
            .first()
        )
        if existing_import:
            return {
                "status": "duplicate_file",
                "message": "This file was already imported (SHA-256 match).",
                "import_id": existing_import.import_id,
                "bank": existing_import.bank,
                "filename": existing_import.filename,
                "transaction_count": existing_import.transaction_count,
                "inserted": 0,
                "skipped_duplicates": 0,
                "preview": parsed.get("preview", []),
                "errors": parsed.get("errors", []),
                "privacy": "local_only",
            }

        existing_keys = {
            row.external_key
            for row in self.db.query(models.WilsonTransaction.external_key)
            .filter(models.WilsonTransaction.user_id == self.user_id)
            .all()
            if row.external_key
        }
        fresh, skipped = deduplicate_transactions(parsed["transactions"], existing_keys)

        if auto_categorize and fresh:
            categorized, cat_stats = categorize_transactions(fresh)
            fresh = categorized
        else:
            cat_stats = {"total": len(fresh), "rule_matched": 0, "needing_review": 0}

        mark_recurring(fresh)

        import_row = models.WilsonImport(
            user_id=self.user_id,
            filename=filename,
            file_hash=file_hash,
            bank=parsed.get("bank"),
            transaction_count=len(fresh),
            date_range_start=parsed.get("date_range_start"),
            date_range_end=parsed.get("date_range_end"),
            import_metadata={"errors": parsed.get("errors", []), "categorization": cat_stats},
        )
        self.db.add(import_row)
        self.db.flush()

        inserted_rows: List[models.WilsonTransaction] = []
        for txn in fresh:
            row = models.WilsonTransaction(
                user_id=self.user_id,
                import_id=import_row.import_id,
                date=txn["date"],
                description=txn["description"],
                amount=float(txn["amount"]),
                category=txn.get("category"),
                category_confidence=txn.get("confidence"),
                categorization_method=txn.get("method"),
                bank=txn.get("bank") or parsed.get("bank"),
                source_file=filename,
                external_key=txn.get("external_key"),
                is_recurring=bool(txn.get("is_recurring")),
                user_verified=False,
            )
            self.db.add(row)
            inserted_rows.append(row)

        self.db.commit()
        self.db.refresh(import_row)

        # Second-pass recurring flags now that IDs exist
        self._refresh_recurring_flags()

        logger.info(
            "Wilson import user=%s file=%s inserted=%s skipped=%s",
            self.user_id,
            filename,
            len(inserted_rows),
            skipped,
        )

        return {
            "status": "imported",
            "import_id": import_row.import_id,
            "bank": parsed.get("bank"),
            "filename": filename,
            "file_hash": file_hash,
            "transaction_count": len(fresh),
            "inserted": len(fresh),
            "skipped_duplicates": skipped,
            "categorization": cat_stats,
            "preview": [
                {
                    "date": t["date"],
                    "description": t["description"],
                    "amount": t["amount"],
                    "category": t.get("category"),
                }
                for t in fresh[:5]
            ],
            "date_range_start": parsed.get("date_range_start"),
            "date_range_end": parsed.get("date_range_end"),
            "errors": parsed.get("errors", []),
            "privacy": "local_only",
        }

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
        q = self.db.query(models.WilsonTransaction).filter(
            models.WilsonTransaction.user_id == self.user_id
        )
        if category:
            q = q.filter(models.WilsonTransaction.category == category)
        if start_date:
            q = q.filter(models.WilsonTransaction.date >= start_date)
        if end_date:
            q = q.filter(models.WilsonTransaction.date <= end_date)
        if uncategorized_only:
            q = q.filter(
                (models.WilsonTransaction.category.is_(None))
                | (models.WilsonTransaction.category == "Other")
            )
        if search:
            like = f"%{search}%"
            q = q.filter(models.WilsonTransaction.description.ilike(like))

        total = q.count()
        rows = (
            q.order_by(models.WilsonTransaction.date.desc(), models.WilsonTransaction.id.desc())
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
            self.db.query(models.WilsonTransaction)
            .filter(
                models.WilsonTransaction.id == transaction_id,
                models.WilsonTransaction.user_id == self.user_id,
            )
            .first()
        )
        if not row:
            return {}

        if category is not None:
            if category not in WILSON_CATEGORIES:
                raise ValueError(f"Invalid category. Must be one of: {WILSON_CATEGORIES}")
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
            self.db.query(models.WilsonTransaction)
            .filter(
                models.WilsonTransaction.user_id == self.user_id,
                (models.WilsonTransaction.category.is_(None))
                | (models.WilsonTransaction.category == "Other")
                | (models.WilsonTransaction.user_verified.is_(False)),
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
            "categories": WILSON_CATEGORIES,
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
            self.db.query(models.WilsonImport)
            .filter(models.WilsonImport.user_id == self.user_id)
            .order_by(models.WilsonImport.imported_at.desc())
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
            "categories": WILSON_CATEGORIES,
            "privacy": "local_only",
            "answer_text": summary.get("answer_text"),
        }

    def context_for_ask_cfo(self) -> Optional[str]:
        """Compact local ledger context for AgentCFO prompts."""
        count = (
            self.db.query(models.WilsonTransaction)
            .filter(models.WilsonTransaction.user_id == self.user_id)
            .count()
        )
        if count == 0:
            return None

        summary = self.summary()
        anomalies = self.anomalies()
        lines = [
            "WILSON LOCAL LEDGER (privacy-first, computed on-device):",
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
            "prefer these Wilson figures over estimates."
        )
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _all_txn_dicts(self) -> List[Dict[str, Any]]:
        rows = (
            self.db.query(models.WilsonTransaction)
            .filter(models.WilsonTransaction.user_id == self.user_id)
            .order_by(models.WilsonTransaction.date.asc())
            .all()
        )
        return [self._txn_dict(r) for r in rows]

    @staticmethod
    def _txn_dict(row: models.WilsonTransaction) -> Dict[str, Any]:
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
            self.db.query(models.WilsonTransaction)
            .filter(
                models.WilsonTransaction.user_id == self.user_id,
                models.WilsonTransaction.id.in_(recurring_ids),
            )
            .update({models.WilsonTransaction.is_recurring: True}, synchronize_session=False)
        )
        self.db.commit()
