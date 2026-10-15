"""Agent 2: Cash Flow Forecasting"""

from app.agents.base_agent import BaseAgent
from typing import Dict, Any
import logging
import json
import re

logger = logging.getLogger(__name__)


class CashFlowForecaster(BaseAgent):
    """Predict future cash position based on historical data"""

    SYSTEM_PROMPT = """You are a Cash Flow Forecasting Agent. Based on historical financial data, predict future cash positions.
Calculate burn rate, runway, and project cash balance at 3-month and 6-month intervals.
Identify trends in revenue and expenses. Flag potential cash shortfall dates.
Return results in strict JSON format with clear confidence levels.

Output format must be valid JSON matching this structure:
{
  "current_cash_position": float,
  "monthly_burn_rate": float,
  "runway_months": float,
  "forecasts": {
    "3_month": {
      "date": str,
      "projected_balance": float,
      "confidence": str
    },
    "6_month": {
      "date": str,
      "projected_balance": float,
      "confidence": str
    }
  },
  "trends": {
    "revenue_trend": str,
    "expense_trend": str,
    "revenue_growth_rate": float
  },
  "risk_alerts": [
    {"type": str, "message": str, "date": str}
  ]
}"""

    def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute cash flow forecasting"""
        logger.info("Starting Cash Flow Forecaster execution")

        result, exec_time = self.run_with_retry(
            context=context,
            system_prompt=self.SYSTEM_PROMPT,
            temperature=0.3,
            max_tokens=800,
            reasoning_effort="medium",
        )
        return self._apply_deterministic_cashflow_calculations(result, context)

    def _build_prompt(self, context: Dict[str, Any]) -> str:
        """Build prompt for cash flow forecasting"""
        financial_data = context.get("financial_data", {})

        prompt = f"""Based on the following financial data, forecast cash flow for the next 3 and 6 months:

Financial Analysis Data:
{json.dumps(financial_data, indent=2)}

Tasks:
1. Calculate current cash position (assets minus immediate liabilities)
2. Calculate monthly burn rate based on expense patterns
3. Project runway (months until cash depletes at current burn rate)
4. Forecast cash position at 3-month and 6-month marks
5. Identify revenue and expense trends (increasing/stable/decreasing)
6. Calculate revenue growth rate
7. Flag potential cash shortfall dates with specific alerts

Provide confidence levels:
- "high" if data is consistent and trends are clear
- "medium" if some uncertainty exists
- "low" if data is limited or inconsistent

Return only valid JSON without any markdown formatting or explanations."""

        return prompt

    def _validate_output(self, output: Dict[str, Any]) -> bool:
        """Validate cash flow forecaster output"""
        if not super()._validate_output(output):
            return False

        required_keys = ["current_cash_position", "monthly_burn_rate", "runway_months", "forecasts", "trends"]

        for key in required_keys:
            if key not in output:
                logger.warning(f"Missing required key in output: {key}")

        return True

    def _apply_deterministic_cashflow_calculations(self, output: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Deterministically recompute burn rate and runway from financial totals."""
        if not isinstance(output, dict):
            output = {}

        financial_data = context.get("financial_data", {}) or {}

        revenue_total = self._to_float(financial_data.get("revenue", {}).get("total"))
        expenses_total = self._to_float(financial_data.get("expenses", {}).get("total"))
        cash_equivalents = self._to_float(financial_data.get("cash_and_cash_equivalents"))

        if revenue_total is None:
            revenue_total = self._to_float(financial_data.get("financial_health", {}).get("total_revenue"))
        if expenses_total is None:
            expenses_total = self._to_float(financial_data.get("financial_health", {}).get("total_expenses"))

        revenue_total = self._round2(revenue_total or 0.0)
        expenses_total = self._round2(expenses_total or 0.0)
        cash_equivalents = self._round2(cash_equivalents or 0.0)

        # Strict formulas
        monthly_burn_rate = self._round2(expenses_total / 12) if expenses_total > 0 else 0.0
        runway_months = self._round2(cash_equivalents / monthly_burn_rate) if monthly_burn_rate > 0 else 0.0

        output["current_cash_position"] = cash_equivalents
        output["monthly_burn_rate"] = monthly_burn_rate
        output["runway_months"] = runway_months

        logger.info(
            "CashFlowForecaster deterministic metrics: burn=%.2f runway=%.2f",
            monthly_burn_rate,
            runway_months,
        )

        return output

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
