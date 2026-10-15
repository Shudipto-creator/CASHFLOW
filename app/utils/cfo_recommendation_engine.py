"""
CFO Recommendation Engine
Analyzes financial data and generates strategic, scenario-aware recommendations
"""

from typing import Dict, Any, List
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class RiskAlert:
    """Risk alert classification"""
    category: str  # "liquidity", "debt", "profitability", "operational"
    level: str     # "HIGH", "MEDIUM", "LOW"
    message: str


@dataclass
class CFORecommendation:
    """Structured CFO recommendation"""
    priority: int
    title: str
    description: str
    impact: str        # "high", "medium", "low"
    effort: str        # "high", "medium", "low"
    timeline: str      # "immediate", "1-3 months", "3-6 months"
    category: str      # Financial strategy area


class CFORecommendationEngine:
    """Generate CFO-level strategic recommendations based on financial scenarios"""

    def __init__(self):
        self.recommendations: List[CFORecommendation] = []
        self.risk_alerts: List[RiskAlert] = []

    def analyze_and_recommend(self, financial_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze financial data, detect scenarios, assess risks, and generate recommendations.
        
        Args:
            financial_data: Dict containing financial metrics from FinancialAnalyzer
            
        Returns:
            Dict with risk_alerts, detected_scenario, and recommendations
        """
        # Extract metrics
        revenue = self._get_float(financial_data, ["financial_health.total_revenue", "revenue.total"])
        expenses = self._get_float(financial_data, ["financial_health.total_expenses", "expenses.total"])
        cash_equiv = self._get_float(financial_data, ["cash_and_cash_equivalents"])
        net_margin = self._get_float(financial_data, ["financial_health.net_profit_margin_percent", "metrics.net_profit_margin"])
        monthly_burn = self._get_float(financial_data, ["cashflow_forecast.monthly_burn_rate", "metrics.monthly_burn_rate"])
        runway = self._get_float(financial_data, ["cashflow_forecast.runway_months", "metrics.runway_months"])
        
        # Extract optional balance sheet data
        total_assets = self._get_float(financial_data, ["balance_sheet.total_assets"])
        total_liabilities = self._get_float(financial_data, ["balance_sheet.total_liabilities"])
        receivables = self._get_float(financial_data, ["balance_sheet.receivables"])
        
        # Step 1: Detect financial scenario and risks
        self._detect_scenarios_and_risks(
            revenue, expenses, cash_equiv, net_margin, 
            monthly_burn, runway, total_assets, total_liabilities, receivables
        )
        
        # Step 2: Generate scenario-aware recommendations
        self._generate_recommendations(
            revenue, expenses, cash_equiv, net_margin,
            monthly_burn, runway, total_assets, total_liabilities, receivables
        )
        
        # Step 3: Prioritize and limit to 5 actions
        self.recommendations.sort(key=lambda r: r.priority)
        recommendations = self.recommendations[:5]
        
        return {
            "risk_alerts": [
                {"category": r.category, "level": r.level, "message": r.message}
                for r in self.risk_alerts
            ],
            "detected_scenarios": self._build_scenario_summary(),
            "recommendations": [
                {
                    "priority": r.priority,
                    "title": r.title,
                    "description": r.description,
                    "impact": r.impact,
                    "effort": r.effort,
                    "timeline": r.timeline,
                    "category": r.category,
                }
                for r in recommendations
            ],
        }

    def _detect_scenarios_and_risks(
        self,
        revenue: float,
        expenses: float,
        cash_equiv: float,
        net_margin: float,
        monthly_burn: float,
        runway: float,
        total_assets: float,
        total_liabilities: float,
        receivables: float,
    ):
        """Detect financial risks and scenarios"""
        self.detected_scenarios = []
        self.risk_alerts = []

        # --- Liquidity Risk ---
        if runway < 3:
            self.risk_alerts.append(
                RiskAlert("liquidity", "HIGH", f"Cash runway critically low at {runway:.2f} months")
            )
            self.detected_scenarios.append("Low Cash Runway (< 3 months)")
        elif runway < 6:
            self.risk_alerts.append(
                RiskAlert("liquidity", "MEDIUM", f"Cash runway limited at {runway:.2f} months")
            )
        else:
            self.risk_alerts.append(
                RiskAlert("liquidity", "LOW", f"Healthy cash position with {runway:.2f} months runway")
            )

        # --- Burn Rate Risk ---
        if monthly_burn > revenue * 0.5:  # Expenses > 50% monthly revenue
            self.risk_alerts.append(
                RiskAlert("operational", "HIGH", f"High burn rate of ${monthly_burn:,.0f}/month relative to revenue")
            )
            self.detected_scenarios.append("High Burn Rate")

        # --- Profitability Risk ---
        if revenue <= expenses:
            self.risk_alerts.append(
                RiskAlert("profitability", "HIGH", "Company is operating at loss or breakeven")
            )
            self.detected_scenarios.append("Loss-making Company")
        elif net_margin < 10:
            self.risk_alerts.append(
                RiskAlert("profitability", "MEDIUM", f"Low net profit margin of {net_margin:.2f}%")
            )
            self.detected_scenarios.append("Low Profit Margin (< 10%)")
        else:
            self.risk_alerts.append(
                RiskAlert("profitability", "LOW", f"Healthy profit margin of {net_margin:.2f}%")
            )

        # --- Debt Risk ---
        if total_liabilities and total_assets:
            debt_ratio = total_liabilities / total_assets if total_assets > 0 else 0
            if debt_ratio > 0.7:
                self.risk_alerts.append(
                    RiskAlert("debt", "HIGH", f"High debt-to-asset ratio of {debt_ratio:.2f}")
                )
                self.detected_scenarios.append("High Debt / Liabilities")
            elif debt_ratio > 0.5:
                self.risk_alerts.append(
                    RiskAlert("debt", "MEDIUM", f"Moderate debt-to-asset ratio of {debt_ratio:.2f}")
                )
            else:
                self.risk_alerts.append(
                    RiskAlert("debt", "LOW", f"Healthy debt-to-asset ratio of {debt_ratio:.2f}")
                )

        # --- Working Capital Risk ---
        if receivables and receivables > revenue * 0.3:  # Receivables > 30% revenue
            self.risk_alerts.append(
                RiskAlert("operational", "MEDIUM", "High receivables locking working capital")
            )
            self.detected_scenarios.append("High Receivables Locking Working Capital")

    def _generate_recommendations(
        self,
        revenue: float,
        expenses: float,
        cash_equiv: float,
        net_margin: float,
        monthly_burn: float,
        runway: float,
        total_assets: float,
        total_liabilities: float,
        receivables: float,
    ):
        """Generate CFO-level strategic recommendations based on financial scenario"""
        self.recommendations = []
        priority = 1

        # --- PRIORITY 1: Liquidity Crisis ---
        if runway < 3:
            self.recommendations.append(
                CFORecommendation(
                    priority=priority,
                    title="Secure Emergency Funding",
                    description=f"With only {runway:.2f} months of runway, immediate capital injection is critical. Explore bridge financing, credit lines, or equity fundraising to extend cash position. Without action, company faces insolvency within {int(runway)} months.",
                    impact="high",
                    effort="high",
                    timeline="immediate",
                    category="Debt & Financing Strategy",
                )
            )
            priority += 1

        # --- PRIORITY: Cost Reduction if Burning Too Fast ---
        if runway < 6 and monthly_burn > 0:
            self.recommendations.append(
                CFORecommendation(
                    priority=priority,
                    title="Aggressive Cost Reduction Program",
                    description=f"Monthly burn rate of ${monthly_burn:,.0f} is unsustainable. Implement immediate cost optimization targeting 20-30% expense reduction. Focus on discretionary spending, vendor renegotiation, and operational efficiency.",
                    impact="high",
                    effort="medium",
                    timeline="immediate",
                    category="Cost Optimization",
                )
            )
            priority += 1

        # --- PRIORITY: Accelerate Revenue if Healthy Margins ---
        if runway > 6 and net_margin > 10:
            self.recommendations.append(
                CFORecommendation(
                    priority=priority,
                    title="Accelerate Revenue Growth Initiatives",
                    description=f"Company has healthy profitability ({net_margin:.2f}% margin) and stable runway. Reinvest profits into sales & marketing to drive top-line growth. Consider market expansion or product line diversification.",
                    impact="high",
                    effort="medium",
                    timeline="1-3 months",
                    category="Revenue Growth Strategy",
                )
            )
            priority += 1

        # --- PRIORITY: Optimize Working Capital ---
        if receivables and receivables > revenue * 0.2:
            self.recommendations.append(
                CFORecommendation(
                    priority=priority,
                    title="Optimize Receivables Collection",
                    description=f"Receivables of ${receivables:,.0f} represent significant working capital lock-up. Implement stricter credit terms, offer early-pay discounts, and establish automated collection processes. This can free up ${receivables * 0.2:,.0f}+ in cash.",
                    impact="medium",
                    effort="medium",
                    timeline="1-3 months",
                    category="Cash Flow Management",
                )
            )
            priority += 1

        # --- PRIORITY: Debt Refinancing if High Leverage ---
        if total_liabilities and total_assets and (total_liabilities / total_assets) > 0.6:
            self.recommendations.append(
                CFORecommendation(
                    priority=priority,
                    title="Restructure High-Cost Debt",
                    description=f"Debt-to-asset ratio of {(total_liabilities / total_assets):.2f} indicates overleveraging. Explore refinancing at lower rates, extend payment terms, or convert debt to equity. This reduces interest burden and improves cash flow.",
                    impact="medium",
                    effort="high",
                    timeline="3-6 months",
                    category="Debt & Financing Strategy",
                )
            )
            priority += 1

        # --- FILL REMAINING SLOTS WITH OPERATIONAL EFFICIENCY ---
        while len(self.recommendations) < 5:
            if len(self.recommendations) == 3 and net_margin < 15:
                self.recommendations.append(
                    CFORecommendation(
                        priority=priority,
                        title="Implement Financial Governance Framework",
                        description="Establish monthly P&L reviews, departmental budgets, and KPI tracking. Deploy financial planning tools for forecast accuracy. This ensures early warning signals and disciplined cost control across the organization.",
                        impact="medium",
                        effort="medium",
                        timeline="1-3 months",
                        category="Financial Governance",
                    )
                )
            elif len(self.recommendations) == 4:
                self.recommendations.append(
                    CFORecommendation(
                        priority=priority,
                        title="Build Strategic Cash Reserve",
                        description="Allocate 10-15% of monthly revenue to a dedicated cash reserve. This provides runway extension and enables opportunistic investments. Target 6+ months operating expenses in reserve.",
                        impact="medium",
                        effort="low",
                        timeline="3-6 months",
                        category="Risk Mitigation",
                    )
                )
            else:
                self.recommendations.append(
                    CFORecommendation(
                        priority=priority,
                        title="Accelerate Revenue Collection & Growth",
                        description="Implement aggressive AR collection strategies and expand high-margin product lines. Focus on recurring revenue models to stabilize cash inflows and improve predictability.",
                        impact="medium",
                        effort="medium",
                        timeline="3-6 months",
                        category="Revenue Growth Strategy",
                    )
                )
            priority += 1

    def _build_scenario_summary(self) -> str:
        """Build a one-line summary of detected scenarios"""
        if not self.detected_scenarios:
            return "Healthy company with expansion opportunity"
        return " | ".join(self.detected_scenarios)

    def _get_float(self, data: Dict[str, Any], paths: List[str]) -> float:
        """Extract float value from nested dict using dot-notation paths"""
        for path in paths:
            try:
                value = data
                for key in path.split("."):
                    if isinstance(value, dict):
                        value = value.get(key)
                    else:
                        value = None
                        break
                if value is not None and isinstance(value, (int, float)):
                    return float(value)
            except (KeyError, TypeError, AttributeError):
                continue
        return 0.0
