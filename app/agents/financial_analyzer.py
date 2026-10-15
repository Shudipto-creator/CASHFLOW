"""Agent 1: Financial Data Extraction and Analysis"""

from app.agents.base_agent import BaseAgent
from typing import Dict, Any
import logging
import re

logger = logging.getLogger(__name__)


class FinancialAnalyzer(BaseAgent):
    """Extract and structure financial data from uploaded documents"""

    SYSTEM_PROMPT = """You are a Financial Data Extraction Agent. Extract structured financial data from the provided documents.
Identify revenue streams, expense categories, liabilities, loan EMIs, and tax payments.
Return results in strict JSON format with numerical values only (no currency symbols).
If information is missing or unclear, use null values.

Output format must be valid JSON matching this structure:
{
  "revenue": {
    "total": float,
    "breakdown": [{"category": str, "amount": float}]
  },
  "expenses": {
    "total": float,
    "breakdown": [{"category": str, "amount": float}]
  },
  "liabilities": {
    "total": float,
    "breakdown": [{"type": str, "amount": float, "due_date": str}]
  },
  "loan_emis": [{"lender": str, "amount": float, "frequency": str}],
  "tax_payments": [{"type": str, "amount": float, "date": str}],
  "metrics": {
    "gross_margin": float,
    "net_profit_margin": float,
    "expense_ratio": float
  }
}"""

    def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute financial analysis"""
        logger.info("Starting Financial Analyzer execution")

        result, exec_time = self.run_with_retry(
            context=context,
            system_prompt=self.SYSTEM_PROMPT,
            temperature=0.1,
            max_tokens=1000,
            reasoning_effort="low",
        )
        return self._apply_deterministic_financial_calculations(result, context)

    def _build_prompt(self, context: Dict[str, Any]) -> str:
        """Build prompt for financial analysis"""
        documents_text = context.get("documents_text", "")
        document_types = context.get("document_types", [])

        prompt = f"""Analyze the following financial documents and extract structured data:

Document Types: {', '.join(document_types) if document_types else 'Mixed financial documents'}

Documents Content:
{documents_text[:15000]}

Extract all financial information including:
- Total revenue and breakdown by categories
- Total expenses and breakdown by categories
- Liabilities with due dates
- Loan EMI information
- Tax payments

Calculate financial metrics:
- Gross margin percentage
- Net profit margin
- Expense ratio

Return only valid JSON without any markdown formatting or explanations."""

        return prompt

    def _validate_output(self, output: Dict[str, Any]) -> bool:
        """Validate financial analyzer output"""
        if not super()._validate_output(output):
            return False

        # Check for required keys
        required_keys = ["revenue", "expenses", "liabilities", "loan_emis", "tax_payments", "metrics"]

        for key in required_keys:
            if key not in output:
                logger.warning(f"Missing required key in output: {key}")
                # Don't fail validation, just warn
        return True

    def _apply_deterministic_financial_calculations(self, output: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Deterministically recompute KPI metrics using strict financial formulas."""
        if not isinstance(output, dict):
            output = {}

        documents_text = context.get("documents_text", "")

        revenue_total = self._to_float(output.get("revenue", {}).get("total"))
        expenses_total = self._to_float(output.get("expenses", {}).get("total"))

        if revenue_total is None:
            revenue_total = self._extract_total_from_text(
                documents_text,
                [
                    r"total\s+revenue[^0-9-]*([\d,]+(?:\.\d+)?)",
                    r"revenue\s+total[^0-9-]*([\d,]+(?:\.\d+)?)",
                ],
            )

        if expenses_total is None:
            expenses_total = self._extract_total_from_text(
                documents_text,
                [
                    r"total\s+operating\s+expenses[^0-9-]*([\d,]+(?:\.\d+)?)",
                    r"total\s+expenses[^0-9-]*([\d,]+(?:\.\d+)?)",
                    r"operating\s+expenses[^0-9-]*([\d,]+(?:\.\d+)?)",
                ],
            )

        cash_equivalents = self._extract_total_from_text(
            documents_text,
            [
                r"cash\s*(?:&|and)\s*cash\s*equivalents[^0-9-]*([\d,]+(?:\.\d+)?)",
                r"cash\s+equivalents[^0-9-]*([\d,]+(?:\.\d+)?)",
            ],
        )

        revenue_total = self._round2(revenue_total or 0.0)
        expenses_total = self._round2(expenses_total or 0.0)
        cash_equivalents = self._round2(cash_equivalents or 0.0)

        # Strict formulas
        net_profit = self._round2(revenue_total - expenses_total)
        net_profit_margin = self._round2((net_profit / revenue_total) * 100) if revenue_total > 0 else 0.0
        monthly_burn_rate = self._round2(expenses_total / 12) if expenses_total > 0 else 0.0
        runway_months = self._round2(cash_equivalents / monthly_burn_rate) if monthly_burn_rate > 0 else 0.0

        output.setdefault("revenue", {})
        output.setdefault("expenses", {})
        output.setdefault("metrics", {})

        output["revenue"]["total"] = revenue_total
        output["expenses"]["total"] = expenses_total
        output["metrics"]["net_profit_margin"] = net_profit_margin
        output["metrics"]["net_profit"] = net_profit
        output["metrics"]["monthly_burn_rate"] = monthly_burn_rate
        output["metrics"]["runway_months"] = runway_months
        output["cash_and_cash_equivalents"] = cash_equivalents

        # Structured deterministic view requested for dashboards/APIs
        output["financial_health"] = {
            "total_revenue": revenue_total,
            "total_expenses": expenses_total,
            "net_profit_margin_percent": net_profit_margin,
        }
        output["cashflow_forecast"] = {
            "monthly_burn_rate": monthly_burn_rate,
            "runway_months": runway_months,
        }

        logger.info(
            "FinancialAnalyzer deterministic metrics: revenue=%.2f expenses=%.2f margin=%.2f burn=%.2f runway=%.2f",
            revenue_total,
            expenses_total,
            net_profit_margin,
            monthly_burn_rate,
            runway_months,
        )

        return output

    def _extract_total_from_text(self, text: str, patterns: list[str]) -> float | None:
        if not text:
            return None

        for pattern in patterns:
            match = re.search(pattern, text, flags=re.IGNORECASE)
            if match:
                parsed = self._to_float(match.group(1))
                if parsed is not None:
                    return parsed
        return None

    def _to_float(self, value: Any) -> float | None:
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return float(value)

        text = str(value).strip()
        if not text:
            return None

        text = text.replace(",", "")
        text = re.sub(r"[^\d.\-]", "", text)
        if text in {"", ".", "-", "-."}:
          return None

        try:
            return float(text)
        except (TypeError, ValueError):
            return None

    def _round2(self, value: float) -> float:
        return round(float(value), 2)
