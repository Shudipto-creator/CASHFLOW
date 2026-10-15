"""Agent 5: Explainability and Recommendations"""

from app.agents.base_agent import BaseAgent
from typing import Dict, Any
import logging
import json

logger = logging.getLogger(__name__)


class ExplainabilityAgent(BaseAgent):
    """Provide clear explanations and actionable recommendations"""

    SYSTEM_PROMPT = """You are a Financial Explainability Agent. Synthesize complex financial data into clear, executive-level insights.
Explain loan rejection reasons in plain language. Provide 3-5 specific, prioritized, actionable recommendations to improve financial health and creditworthiness.
Translate technical metrics into business-focused language.
Your audience is a small business owner without financial expertise.
Return results in strict JSON format.

Output format must be valid JSON matching this structure:
{
  "executive_summary": str,
  "loan_readiness_score": int,
  "loan_analysis": {
    "approval_likelihood": str,
    "strengths": [str],
    "weaknesses": [str],
    "rejection_reasons": [str]
  },
  "recommended_actions": [
    {
      "priority": int,
      "category": str,
      "action": str,
      "impact": str,
      "effort": str,
      "timeline": str,
      "details": str
    }
  ],
  "key_insights": [str],
  "plain_language_metrics": {
    "financial_health": str,
    "cash_position": str,
    "risk_level": str
  }
}"""

    def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute explainability analysis"""
        logger.info("Starting Explainability Agent execution")

        result, exec_time = self.run_with_retry(
            context=context,
            system_prompt=self.SYSTEM_PROMPT,
            temperature=0.5,
            max_tokens=1000,
            reasoning_effort="medium",
        )

        # Ensure recommended_actions is always present with fallback values
        if "recommended_actions" not in result or not result.get("recommended_actions"):
            logger.warning("No recommended_actions in explainability output, using defaults")
            result["recommended_actions"] = self._generate_default_recommendations(context)
        
        return result

    def _generate_default_recommendations(self, context: Dict[str, Any]) -> list:
        """Generate default recommendations if model doesn't provide them"""
        financial_data = context.get("financial_data", {})
        risk_data = context.get("risk_data", {})
        
        recommendations = []
        
        # Check profit margin
        profit_margin = financial_data.get("profit_margin", 0)
        if profit_margin < 0:
            recommendations.append({
                "priority": 1,
                "category": "revenue",
                "action": "Increase revenue through market expansion or pricing optimization",
                "impact": "high",
                "effort": "high",
                "timeline": "3-6 months",
                "details": "Current negative profit margin indicates expenses exceed revenue. Focus on growing top-line revenue or entering new markets."
            })
        
        # Check runway
        runway = financial_data.get("runway_months", 0)
        if runway < 3:
            recommendations.append({
                "priority": 1 if runway < 1 else 2,
                "category": "cash_management",
                "action": "Improve cash management and reduce monthly burn rate",
                "impact": "high",
                "effort": "medium",
                "timeline": "immediate",
                "details": f"With only {runway:.1f} months of runway, immediate action is needed to extend cash position or reduce expenses."
            })
        
        # Check risk score
        risk_score = risk_data.get("risk_score", 0)
        if risk_score > 70:
            recommendations.append({
                "priority": 2,
                "category": "compliance",
                "action": "Address high-risk financial indicators and implement controls",
                "impact": "high",
                "effort": "medium",
                "timeline": "1-3 months",
                "details": "High risk score indicates volatility or structural issues. Implement financial controls and monitoring systems."
            })
        
        # Add general recommendations to reach minimum
        if len(recommendations) < 3:
            recommendations.append({
                "priority": 3,
                "category": "cost_reduction",
                "action": "Conduct operational efficiency review",
                "impact": "medium",
                "effort": "medium",
                "timeline": "1-3 months",
                "details": "Review all operating expenses and identify opportunities for cost optimization."
            })
        
        if len(recommendations) < 3:
            recommendations.append({
                "priority": 4,
                "category": "debt",
                "action": "Develop debt management strategy",
                "impact": "medium",
                "effort": "medium",
                "timeline": "3-6 months",
                "details": "Create a plan to manage and optimize debt obligations."
            })
        
        return recommendations[:5]  # Return max 5 recommendations

    def _build_prompt(self, context: Dict[str, Any]) -> str:
        """Build prompt for explainability"""
        financial_data = context.get("financial_data", {})
        cashflow_data = context.get("cashflow_data", {})
        risk_data = context.get("risk_data", {})
        compliance_data = context.get("compliance_data", {})

        prompt = f"""Synthesize all financial analysis into clear, actionable insights for a business owner:

Financial Analysis:
{json.dumps(financial_data, indent=2)}

Cash Flow Forecast:
{json.dumps(cashflow_data, indent=2)}

Risk Assessment:
{json.dumps(risk_data, indent=2)}

Compliance & Automation:
{json.dumps(compliance_data, indent=2)}

Tasks:
1. Write executive summary (2-3 paragraphs):
   - Current financial situation overview
   - Key opportunities and challenges
   - Most critical actions needed
   - Use business-focused language, not technical jargon

2. Calculate loan readiness score (0-100):
   - Based on: cash position, revenue trends, debt ratios, risk factors
   - 80-100: Excellent, likely approval
   - 60-79: Good, approval likely with conditions
   - 40-59: Fair, approval uncertain
   - 0-39: Poor, approval unlikely

3. Loan analysis:
   - Approval likelihood: "high", "medium", "low"
   - List 3-5 strengths (positive factors)
   - List 3-5 weaknesses (areas of concern)
   - If likelihood is not "high", explain specific rejection reasons

4. Provide 3-5 recommended actions:
   - Priority: 1 (most urgent) to 5 (less urgent)
   - Categories: "revenue", "cost_reduction", "cash_management", "debt", "compliance"
   - Impact: "high", "medium", "low" (on financial health)
   - Effort: "high", "medium", "low" (to implement)
   - Timeline: "immediate" (<1 month), "1-3 months", "3-6 months"
   - Detailed explanation of action and expected benefits

5. Provide 3-5 key insights:
   - Important observations about the business
   - Patterns or trends to be aware of

6. Translate metrics to plain language:
   - Financial health: "Excellent", "Good", "Fair", "Poor"
   - Cash position: "Strong", "Adequate", "Tight", "Critical"
   - Risk level: "Low", "Moderate", "High", "Critical"

Return only valid JSON without any markdown formatting or explanations."""

        return prompt

    def _validate_output(self, output: Dict[str, Any]) -> bool:
        """Validate explainability agent output"""
        if not super()._validate_output(output):
            return False

        required_keys = [
            "executive_summary",
            "loan_readiness_score",
            "loan_analysis",
            "recommended_actions",
            "key_insights",
            "plain_language_metrics",
        ]

        for key in required_keys:
            if key not in output:
                logger.warning(f"Missing required key in output: {key}")

        return True
