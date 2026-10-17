"""Rule + sklearn local financial analyzer (No-AWS mode)."""

from __future__ import annotations

import logging
import re
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline

from app.utils.cfo_recommendation_engine import CFORecommendationEngine
from app.utils.financial_metrics import compute_loan_readiness_score

logger = logging.getLogger(__name__)


def _round2(value: Optional[float]) -> float:
    try:
        return round(float(value or 0.0), 2)
    except (TypeError, ValueError):
        return 0.0


class LocalFinancialAnalyzer:
    """
    Offline analyzer that produces the same report sections as the AWS agents
    using regex extraction, a tiny expense classifier, and rule-based scoring.
    """

    def __init__(self):
        self._expense_clf = self._build_expense_classifier()
        self._cfo_engine = CFORecommendationEngine()

    def analyze(self, documents_text: str, document_types: Optional[List[str]] = None) -> Dict[str, Any]:
        document_types = document_types or ["financial_document"]
        text = documents_text or ""

        financial = self._extract_financial_health(text)
        cashflow = self._build_cashflow(financial, text)
        risk = self._build_risk(financial, cashflow)
        loan_score = compute_loan_readiness_score(
            profit_margin=_round2(financial.get("metrics", {}).get("net_profit_margin")),
            runway_months=_round2(cashflow.get("runway_months")),
            burn_rate=_round2(cashflow.get("monthly_burn_rate")),
            risk_score=_round2(risk.get("risk_score")),
        )
        compliance = self._build_compliance(financial)
        explainability = self._build_explainability(financial, cashflow, risk, loan_score)

        return {
            "section_1_financial_health": financial,
            "section_2_cash_flow_forecast": cashflow,
            "section_3_risk_alerts": risk,
            "section_4_compliance_automation": compliance,
            "section_5_loan_readiness_score": loan_score,
            "section_6_recommended_actions": explainability,
            "loan_readiness_score": loan_score,
            "processing_mode": "local",
            "document_types": document_types,
        }

    # ------------------------------------------------------------------
    # Expense line classifier
    # ------------------------------------------------------------------

    def _build_expense_classifier(self) -> Pipeline:
        samples = [
            ("salary payroll wages compensation", "salary"),
            ("rent lease office space premises", "rent"),
            ("utilities electricity water internet telecom", "utilities"),
            ("marketing ads advertising campaign seo", "marketing"),
            ("software saas subscription license cloud", "software"),
            ("travel flight hotel taxi transportation", "travel"),
            ("inventory raw materials supplier purchase cogs", "cogs"),
            ("legal accounting audit professional fees", "professional_fees"),
            ("tax gst tds income tax payment", "tax"),
            ("loan emi interest repayment debt service", "debt_service"),
            ("miscellaneous office supplies stationery", "other"),
        ]
        texts, labels = zip(*samples)
        pipeline = Pipeline(
            [
                ("tfidf", TfidfVectorizer(ngram_range=(1, 2), max_features=1000)),
                ("clf", LogisticRegression(max_iter=300)),
            ]
        )
        pipeline.fit(list(texts), list(labels))
        return pipeline

    def classify_expense_line(self, description: str) -> str:
        if not description.strip():
            return "other"
        return str(self._expense_clf.predict([description.lower()])[0])

    # ------------------------------------------------------------------
    # Extraction helpers
    # ------------------------------------------------------------------

    def _extract_amount(self, text: str, patterns: List[str]) -> Optional[float]:
        for pattern in patterns:
            match = re.search(pattern, text, flags=re.IGNORECASE)
            if not match:
                continue
            raw = match.group(1).replace(",", "").strip()
            try:
                return float(raw)
            except ValueError:
                continue
        return None

    def _extract_labeled_amounts(self, text: str) -> List[Tuple[str, float]]:
        """Pull 'label: 1,234.56' style pairs from text/JSON dumps."""
        pairs: List[Tuple[str, float]] = []
        pattern = re.compile(
            r"([A-Za-z][A-Za-z0-9 &_/()-]{2,40})\s*[:=\-]\s*\$?\s*([\d,]+\.?\d*)",
            flags=re.IGNORECASE,
        )
        for match in pattern.finditer(text[:50000]):
            label = match.group(1).strip()
            try:
                amount = float(match.group(2).replace(",", ""))
            except ValueError:
                continue
            if amount <= 0:
                continue
            pairs.append((label, amount))
        return pairs

    def _extract_financial_health(self, text: str) -> Dict[str, Any]:
        revenue_total = self._extract_amount(
            text,
            [
                r"total\s+revenue[^0-9-]*([\d,]+(?:\.\d+)?)",
                r"\"revenue\"\s*:\s*\{[^}]*\"total\"\s*:\s*([\d,]+(?:\.\d+)?)",
                r"revenue\s*[:=]\s*\$?\s*([\d,]+(?:\.\d+)?)",
                r"sales\s*[:=]\s*\$?\s*([\d,]+(?:\.\d+)?)",
            ],
        )
        expenses_total = self._extract_amount(
            text,
            [
                r"total\s+operating\s+expenses[^0-9-]*([\d,]+(?:\.\d+)?)",
                r"total\s+expenses[^0-9-]*([\d,]+(?:\.\d+)?)",
                r"\"expenses\"\s*:\s*\{[^}]*\"total\"\s*:\s*([\d,]+(?:\.\d+)?)",
                r"operating\s+expenses\s*[:=]\s*\$?\s*([\d,]+(?:\.\d+)?)",
            ],
        )
        cash = self._extract_amount(
            text,
            [
                r"cash\s*(?:&|and)\s*cash\s*equivalents[^0-9-]*([\d,]+(?:\.\d+)?)",
                r"cash\s+equivalents[^0-9-]*([\d,]+(?:\.\d+)?)",
                r"current\s+cash[^0-9-]*([\d,]+(?:\.\d+)?)",
                r"closing\s+balance[^0-9-]*([\d,]+(?:\.\d+)?)",
            ],
        )
        liabilities_total = self._extract_amount(
            text,
            [
                r"total\s+liabilities[^0-9-]*([\d,]+(?:\.\d+)?)",
                r"liabilities\s*[:=]\s*\$?\s*([\d,]+(?:\.\d+)?)",
            ],
        )

        labeled = self._extract_labeled_amounts(text)
        revenue_breakdown: List[Dict[str, Any]] = []
        expense_breakdown_map: Dict[str, float] = defaultdict(float)

        revenue_keywords = ("revenue", "sales", "income", "receipt")
        expense_keywords = ("expense", "cost", "salary", "rent", "utilities", "cogs", "marketing")

        for label, amount in labeled[:80]:
            lower = label.lower()
            if any(k in lower for k in revenue_keywords) and "expense" not in lower:
                revenue_breakdown.append({"category": label, "amount": _round2(amount)})
                if revenue_total is None:
                    revenue_total = (revenue_total or 0.0) + amount
            elif any(k in lower for k in expense_keywords) or "payment" in lower:
                category = self.classify_expense_line(label)
                expense_breakdown_map[category] += amount
                if expenses_total is None:
                    expenses_total = (expenses_total or 0.0) + amount

        # Fallback: harvest large numeric values if totals still missing
        if revenue_total is None or expenses_total is None:
            numbers = [
                float(n.replace(",", ""))
                for n in re.findall(r"\b\d{1,3}(?:,\d{3})+(?:\.\d+)?\b|\b\d+\.\d{2}\b", text[:20000])
            ]
            numbers = sorted([n for n in numbers if 100 <= n <= 1e9], reverse=True)
            if revenue_total is None and numbers:
                revenue_total = numbers[0]
            if expenses_total is None and len(numbers) > 1:
                expenses_total = numbers[1]

        revenue_total = _round2(revenue_total)
        expenses_total = _round2(expenses_total)
        cash = _round2(cash)
        liabilities_total = _round2(liabilities_total)

        net_profit = _round2(revenue_total - expenses_total)
        net_margin = _round2((net_profit / revenue_total) * 100) if revenue_total > 0 else 0.0
        expense_ratio = _round2((expenses_total / revenue_total) * 100) if revenue_total > 0 else 0.0
        gross_margin = _round2(max(0.0, 100.0 - expense_ratio * 0.7))

        expense_breakdown = [
            {"category": cat, "amount": _round2(amt)}
            for cat, amt in sorted(expense_breakdown_map.items(), key=lambda x: x[1], reverse=True)
        ]
        if not expense_breakdown and expenses_total > 0:
            expense_breakdown = [{"category": "operating", "amount": expenses_total}]

        if not revenue_breakdown and revenue_total > 0:
            revenue_breakdown = [{"category": "total_revenue", "amount": revenue_total}]

        loan_emis = []
        emi_match = re.search(
            r"(?:emi|loan\s+payment)[^0-9]{0,20}([\d,]+(?:\.\d+)?)",
            text,
            flags=re.IGNORECASE,
        )
        if emi_match:
            loan_emis.append(
                {
                    "lender": "Detected Lender",
                    "amount": _round2(float(emi_match.group(1).replace(",", ""))),
                    "frequency": "monthly",
                }
            )

        return {
            "revenue": {"total": revenue_total, "breakdown": revenue_breakdown[:10]},
            "expenses": {"total": expenses_total, "breakdown": expense_breakdown[:10]},
            "liabilities": {
                "total": liabilities_total,
                "breakdown": (
                    [{"type": "total_liabilities", "amount": liabilities_total, "due_date": None}]
                    if liabilities_total > 0
                    else []
                ),
            },
            "loan_emis": loan_emis,
            "tax_payments": [],
            "cash_and_cash_equivalents": cash,
            "metrics": {
                "gross_margin": gross_margin,
                "net_profit_margin": net_margin,
                "expense_ratio": expense_ratio,
                "net_profit": net_profit,
                "monthly_burn_rate": _round2(expenses_total / 12) if expenses_total > 0 else 0.0,
                "runway_months": (
                    _round2(cash / (expenses_total / 12)) if expenses_total > 0 and cash > 0 else 0.0
                ),
            },
            "source": "local_ml_analyzer",
        }

    def _build_cashflow(self, financial: Dict[str, Any], text: str) -> Dict[str, Any]:
        metrics = financial.get("metrics", {})
        cash = _round2(financial.get("cash_and_cash_equivalents"))
        burn = _round2(metrics.get("monthly_burn_rate"))
        runway = _round2(metrics.get("runway_months"))
        revenue = _round2(financial.get("revenue", {}).get("total"))
        expenses = _round2(financial.get("expenses", {}).get("total"))

        now = datetime.utcnow()
        f3 = _round2(cash - burn * 3)
        f6 = _round2(cash - burn * 6)

        growth = 0.0
        if revenue > 0 and expenses > 0:
            growth = _round2(((revenue - expenses) / revenue) * 100)

        alerts = []
        if runway > 0 and runway < 3:
            shortfall_date = (now + timedelta(days=int(runway * 30))).strftime("%Y-%m-%d")
            alerts.append(
                {
                    "type": "cash_shortfall",
                    "message": f"Projected cash shortfall within {runway:.1f} months",
                    "date": shortfall_date,
                }
            )

        return {
            "current_cash_position": cash,
            "monthly_burn_rate": burn,
            "runway_months": runway,
            "forecasts": {
                "3_month": {
                    "date": (now + timedelta(days=90)).strftime("%Y-%m-%d"),
                    "projected_balance": f3,
                    "confidence": "medium",
                },
                "6_month": {
                    "date": (now + timedelta(days=180)).strftime("%Y-%m-%d"),
                    "projected_balance": f6,
                    "confidence": "low" if runway < 6 else "medium",
                },
            },
            "trends": {
                "revenue_trend": "stable" if growth >= 0 else "decreasing",
                "expense_trend": "stable",
                "revenue_growth_rate": growth,
            },
            "risk_alerts": alerts,
            "source": "local_ml_analyzer",
        }

    def _build_risk(self, financial: Dict[str, Any], cashflow: Dict[str, Any]) -> Dict[str, Any]:
        revenue = _round2(financial.get("revenue", {}).get("total"))
        expenses = _round2(financial.get("expenses", {}).get("total"))
        liabilities = _round2(financial.get("liabilities", {}).get("total"))
        margin = _round2(financial.get("metrics", {}).get("net_profit_margin"))
        runway = _round2(cashflow.get("runway_months"))
        burn = _round2(cashflow.get("monthly_burn_rate"))

        score = 20
        factors = []

        if margin < 0:
            score += 25
            factors.append(
                {
                    "category": "profitability",
                    "severity": "high",
                    "description": "Negative net profit margin",
                    "evidence": [f"Net profit margin={margin}%"],
                    "recommendation": "Cut non-essential costs and improve pricing/margins",
                }
            )
        elif margin < 8:
            score += 12
            factors.append(
                {
                    "category": "profitability",
                    "severity": "medium",
                    "description": "Thin profit margins",
                    "evidence": [f"Net profit margin={margin}%"],
                    "recommendation": "Target expense ratio reduction of 5-10%",
                }
            )

        if runway < 3:
            score += 30
            factors.append(
                {
                    "category": "liquidity",
                    "severity": "critical" if runway < 1.5 else "high",
                    "description": "Short cash runway",
                    "evidence": [f"Runway={runway} months", f"Burn=${burn}"],
                    "recommendation": "Extend runway via cost freeze or bridge financing",
                }
            )
        elif runway < 6:
            score += 15
            factors.append(
                {
                    "category": "liquidity",
                    "severity": "medium",
                    "description": "Moderate runway pressure",
                    "evidence": [f"Runway={runway} months"],
                    "recommendation": "Build 2+ months additional cash buffer",
                }
            )

        dti = _round2((liabilities / revenue) * 100) if revenue > 0 else 0.0
        if dti > 60:
            score += 20
            factors.append(
                {
                    "category": "loan_default",
                    "severity": "high",
                    "description": "High liabilities relative to revenue",
                    "evidence": [f"Debt-to-revenue={dti}%"],
                    "recommendation": "Refinance or negotiate repayment schedules",
                }
            )

        score = int(min(100, max(0, score)))
        if score <= 25:
            level = "low"
        elif score <= 50:
            level = "medium"
        elif score <= 75:
            level = "high"
        else:
            level = "critical"

        liquidity = _round2(
            (cashflow.get("current_cash_position", 0) / liabilities) if liabilities > 0 else 0.0
        )
        emi_total = sum(_round2(e.get("amount")) for e in financial.get("loan_emis", []) or [])
        emi_ratio = _round2((emi_total / revenue) * 100) if revenue > 0 else 0.0

        return {
            "risk_score": score,
            "risk_level": level,
            "risk_factors": factors,
            "anomalies": [],
            "metrics": {
                "debt_to_income_ratio": dti,
                "liquidity_ratio": liquidity,
                "emi_to_revenue_ratio": emi_ratio,
                "expense_to_revenue_ratio": _round2((expenses / revenue) * 100) if revenue > 0 else 0.0,
            },
            "source": "local_ml_analyzer",
        }

    def _build_compliance(self, financial: Dict[str, Any]) -> Dict[str, Any]:
        cfo = self._cfo_engine.analyze_and_recommend(financial)
        now = datetime.utcnow()
        next_month = (now.replace(day=1) + timedelta(days=32)).replace(day=1)

        suggestions = []
        for rec in cfo.get("recommendations", [])[:4]:
            if isinstance(rec, dict):
                suggestions.append(
                    {
                        "category": rec.get("category", "operations"),
                        "description": rec.get("title") or rec.get("description", ""),
                        "potential_savings": rec.get("impact", "medium"),
                        "implementation_complexity": rec.get("effort", "medium"),
                    }
                )

        return {
            "upcoming_deadlines": [
                {
                    "type": "GST",
                    "due_date": next_month.strftime("%Y-%m-%d"),
                    "description": "Monthly GST filing window",
                    "estimated_amount": _round2(financial.get("expenses", {}).get("total", 0) * 0.05),
                    "status": "upcoming",
                }
            ],
            "compliance_issues": [],
            "automation_suggestions": suggestions
            or [
                {
                    "category": "reporting",
                    "description": "Automate monthly P&L and cash runway reports",
                    "potential_savings": "medium",
                    "implementation_complexity": "low",
                }
            ],
            "draft_emails": [
                {
                    "subject": "Upcoming compliance reminder",
                    "body": "Please prepare GST and tax filings for the next cycle based on current expense totals.",
                    "recipient_type": "finance_team",
                }
            ],
            "cfo_recommendations": cfo,
            "source": "local_ml_analyzer",
        }

    def _build_explainability(
        self,
        financial: Dict[str, Any],
        cashflow: Dict[str, Any],
        risk: Dict[str, Any],
        loan_score: float,
    ) -> Dict[str, Any]:
        margin = _round2(financial.get("metrics", {}).get("net_profit_margin"))
        runway = _round2(cashflow.get("runway_months"))
        risk_level = risk.get("risk_level", "unknown")
        revenue = _round2(financial.get("revenue", {}).get("total"))
        expenses = _round2(financial.get("expenses", {}).get("total"))

        strengths = []
        weaknesses = []
        actions = []

        if margin >= 10:
            strengths.append(f"Healthy net margin of {margin}%")
        else:
            weaknesses.append(f"Net margin is only {margin}%")
            actions.append(
                {
                    "priority": 1,
                    "category": "profitability",
                    "action": "Improve contribution margin",
                    "impact": "high",
                    "effort": "medium",
                    "timeline": "1-3 months",
                    "details": "Review pricing and top expense categories to lift margin above 10%.",
                }
            )

        if runway >= 6:
            strengths.append(f"Cash runway of {runway} months")
        else:
            weaknesses.append(f"Cash runway of {runway} months is limited")
            actions.append(
                {
                    "priority": 1,
                    "category": "cash_management",
                    "action": "Extend cash runway",
                    "impact": "high",
                    "effort": "medium",
                    "timeline": "immediate",
                    "details": "Reduce burn or secure short-term financing to reach 6+ months runway.",
                }
            )

        if risk_level in ("high", "critical"):
            weaknesses.append(f"Overall risk level is {risk_level}")
            actions.append(
                {
                    "priority": 2,
                    "category": "risk",
                    "action": "Address top risk factors",
                    "impact": "high",
                    "effort": "high",
                    "timeline": "1-3 months",
                    "details": "Prioritize liquidity and debt-service risks flagged by the local analyzer.",
                }
            )

        if not actions:
            actions.append(
                {
                    "priority": 3,
                    "category": "operations",
                    "action": "Maintain monthly financial review cadence",
                    "impact": "medium",
                    "effort": "low",
                    "timeline": "ongoing",
                    "details": "Keep tracking revenue, burn, and runway with local or AWS analysis.",
                }
            )

        likelihood = "high" if loan_score >= 70 else "medium" if loan_score >= 45 else "low"
        summary = (
            f"Local analysis estimates revenue ${revenue:,.2f} against expenses ${expenses:,.2f}. "
            f"Runway is {runway:.1f} months with risk level {risk_level}. "
            f"Loan readiness score is {loan_score:.0f}/100."
        )

        return {
            "executive_summary": summary,
            "loan_readiness_score": int(loan_score),
            "loan_analysis": {
                "approval_likelihood": likelihood,
                "strengths": strengths or ["Stable operating profile under local analysis"],
                "weaknesses": weaknesses or ["No major weaknesses detected"],
                "rejection_reasons": weaknesses[:3] if likelihood == "low" else [],
            },
            "recommended_actions": actions[:5],
            "key_insights": [
                f"Net profit margin: {margin}%",
                f"Monthly burn rate: ${_round2(cashflow.get('monthly_burn_rate')):,.2f}",
                f"Risk score: {risk.get('risk_score', 0)}/100",
            ],
            "plain_language_metrics": {
                "financial_health": "solid" if margin >= 8 and runway >= 4 else "needs attention",
                "cash_position": f"{runway:.1f} months runway",
                "risk_level": str(risk_level),
            },
            "source": "local_ml_analyzer",
        }
