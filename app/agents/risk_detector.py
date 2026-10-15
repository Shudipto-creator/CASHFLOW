"""Agent 3: Risk Detection and Fraud Analysis"""

from app.agents.base_agent import BaseAgent
from typing import Dict, Any
import logging
import json

logger = logging.getLogger(__name__)


class RiskDetector(BaseAgent):
    """Identify financial risks, anomalies, and fraud indicators"""

    SYSTEM_PROMPT = """You are a Financial Risk Detection Agent. Analyze financial data to identify risks, anomalies, and potential fraud indicators.
Flag abnormal spending patterns, assess loan default risk, detect inconsistencies, and calculate risk metrics.
Provide severity ratings and actionable recommendations.
Return results in strict JSON format.

Output format must be valid JSON matching this structure:
{
  "risk_score": int,
  "risk_level": str,
  "risk_factors": [
    {
      "category": str,
      "severity": str,
      "description": str,
      "evidence": [str],
      "recommendation": str
    }
  ],
  "anomalies": [
    {
      "type": str,
      "transaction_id": str,
      "amount": float,
      "date": str,
      "reason": str
    }
  ],
  "metrics": {
    "debt_to_income_ratio": float,
    "liquidity_ratio": float,
    "emi_to_revenue_ratio": float
  }
}"""

    def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute risk detection"""
        logger.info("Starting Risk Detector execution")

        result, exec_time = self.run_with_retry(
            context=context,
            system_prompt=self.SYSTEM_PROMPT,
            temperature=0.2,
            max_tokens=800,
            reasoning_effort="high",
        )

        return result

    def _build_prompt(self, context: Dict[str, Any]) -> str:
        """Build prompt for risk detection"""
        financial_data = context.get("financial_data", {})
        cashflow_data = context.get("cashflow_data", {})

        prompt = f"""Analyze the following financial data for risks and anomalies:

Financial Data:
{json.dumps(financial_data, indent=2)}

Cash Flow Data:
{json.dumps(cashflow_data, indent=2)}

Tasks:
1. Calculate overall risk score (0-100, higher = more risk)
2. Determine risk level: "low" (0-25), "medium" (26-50), "high" (51-75), "critical" (76-100)
3. Identify risk factors in categories:
   - "loan_default": Risk of defaulting on loans
   - "liquidity": Insufficient liquid assets
   - "fraud": Suspicious transaction patterns
   - "inconsistency": Data inconsistencies

4. Detect anomalies:
   - Unusually large transactions
   - Duplicate transactions
   - Suspicious patterns

5. Calculate risk metrics:
   - Debt-to-income ratio (total debt / monthly income)
   - Liquidity ratio (current assets / current liabilities)
   - EMI-to-revenue ratio (total monthly EMI / monthly revenue)

6. Provide actionable recommendations for each risk factor

Return only valid JSON without any markdown formatting or explanations."""

        return prompt

    def _validate_output(self, output: Dict[str, Any]) -> bool:
        """Validate risk detector output"""
        if not super()._validate_output(output):
            return False

        required_keys = ["risk_score", "risk_level", "risk_factors", "anomalies", "metrics"]

        for key in required_keys:
            if key not in output:
                logger.warning(f"Missing required key in output: {key}")

        return True
