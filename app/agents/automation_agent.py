"""Agent 4: Compliance and Automation Suggestions"""

from app.agents.base_agent import BaseAgent
from typing import Dict, Any
import logging
import json
from datetime import datetime
from app.utils.cfo_recommendation_engine import CFORecommendationEngine

logger = logging.getLogger(__name__)


class AutomationAgent(BaseAgent):
    """Generate CFO-level strategic recommendations and identify compliance/automation opportunities"""

    def __init__(self, nova_client):
        super().__init__(nova_client)
        self.cfo_engine = CFORecommendationEngine()

    SYSTEM_PROMPT = """You are a Compliance and Automation Agent. Identify upcoming tax deadlines, check for compliance issues, and suggest automation opportunities.
Generate draft payment reminder emails. Recommend automated GST filing actions.
Focus on Indian tax compliance (GST, Income Tax, TDS).
Return results in strict JSON format with clear deadlines and actionable suggestions.

Output format must be valid JSON matching this structure:
{
  "upcoming_deadlines": [
    {
      "type": str,
      "due_date": str,
      "description": str,
      "estimated_amount": float,
      "status": str
    }
  ],
  "compliance_issues": [
    {
      "type": str,
      "description": str,
      "severity": str,
      "resolution_steps": [str]
    }
  ],
  "automation_suggestions": [
    {
      "category": str,
      "description": str,
      "potential_savings": str,
      "implementation_complexity": str
    }
  ],
  "draft_emails": [
    {
      "subject": str,
      "body": str,
      "recipient_type": str
    }
  ]
}"""

    def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute compliance and automation analysis"""
        logger.info("Starting Automation Agent execution")

        # Get financial data from context
        financial_data = context.get("financial_data", {})
        
        # Generate CFO recommendations using deterministic engine
        cfo_analysis = self.cfo_engine.analyze_and_recommend(financial_data)
        
        # Build structured output with CFO recommendations first
        result, exec_time = self.run_with_retry(
            context=context,
            system_prompt=self.SYSTEM_PROMPT,
            temperature=0.4,
            max_tokens=800,
            reasoning_effort="low",
        )

        # Normalize shape so downstream consumers always get structured arrays.
        result = self._normalize_output(result)
        
        # Merge CFO analysis into agent output
        if isinstance(result, dict):
            result["cfo_strategic_analysis"] = {
                "risk_alerts": cfo_analysis["risk_alerts"],
                "detected_scenarios": cfo_analysis["detected_scenarios"],
                "recommended_actions": cfo_analysis["recommendations"],
            }
        
        return result

    def _normalize_output(self, output: Dict[str, Any]) -> Dict[str, Any]:
        """Coerce model output into the expected compliance schema."""
        if not isinstance(output, dict):
            return {
                "upcoming_deadlines": [],
                "compliance_issues": [],
                "automation_suggestions": [],
                "draft_emails": [],
            }

        normalized = dict(output)

        # Some model responses return a single deadline object at the root.
        if "upcoming_deadlines" not in normalized and all(
            key in normalized for key in ["type", "due_date", "description"]
        ):
            normalized["upcoming_deadlines"] = [
                {
                    "type": normalized.get("type", ""),
                    "due_date": normalized.get("due_date", ""),
                    "description": normalized.get("description", ""),
                    "estimated_amount": float(normalized.get("estimated_amount", 0) or 0),
                    "status": normalized.get("status", "pending"),
                }
            ]

        required_keys = ["upcoming_deadlines", "compliance_issues", "automation_suggestions", "draft_emails"]
        for key in required_keys:
            value = normalized.get(key)
            if isinstance(value, list):
                continue
            if value is None:
                normalized[key] = []
            else:
                normalized[key] = [value] if isinstance(value, dict) else []

        return normalized

    def _build_prompt(self, context: Dict[str, Any]) -> str:
        """Build prompt for compliance and automation"""
        financial_data = context.get("financial_data", {})
        current_date = datetime.now().strftime("%Y-%m-%d")

        prompt = f"""Analyze financial data for compliance and automation opportunities:

Current Date: {current_date}

Financial Data:
{json.dumps(financial_data, indent=2)}

Tasks:
1. Identify upcoming tax deadlines (next 90 days):
   - GST filing deadlines (monthly/quarterly)
   - Income Tax advance tax payments
   - TDS return filing
   - Annual tax return deadlines

2. Check for compliance issues:
   - Late or missed tax payments
   - Missing documentation
   - Regulatory violations
   - Severity levels: "low", "medium", "high"

3. Suggest automation opportunities in categories:
   - "payment": Automated bill payments
   - "filing": Automated tax filing
   - "reporting": Automated financial reporting

   Include:
   - Description of automation
   - Potential time/cost savings
   - Implementation complexity: "low", "medium", "high"

4. Generate 2-3 draft emails:
   - Payment reminders to vendors
   - Tax deadline reminders
   - Recipient types: "vendor", "client", "tax_authority"

Return only valid JSON without any markdown formatting or explanations."""

        return prompt

    def _validate_output(self, output: Dict[str, Any]) -> bool:
        """Validate automation agent output"""
        if not super()._validate_output(output):
            return False

        output = self._normalize_output(output)
        required_keys = ["upcoming_deadlines", "compliance_issues", "automation_suggestions", "draft_emails"]

        for key in required_keys:
            if key not in output:
                logger.warning(f"Missing required key in output: {key}")

        return True
