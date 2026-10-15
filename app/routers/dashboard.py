"""Financial Intelligence Dashboard endpoints"""

import json
import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from app.database import get_db
from app import models
from app.dependencies import get_current_user
from app.services.nova_client import NovaClient

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


# =====================================================================
# Pydantic Models
# =====================================================================

class WaterfallItem(BaseModel):
    name: str
    value: float
    itemStyle: Optional[Dict[str, Any]] = None


class RevenueWaterfall(BaseModel):
    items: List[WaterfallItem]
    total: float


class VarianceItem(BaseModel):
    category: str
    budget: float
    actual: float
    variance_percent: float


class TrendPoint(BaseModel):
    month: str
    value: float


class BurnRatePoint(BaseModel):
    month: str
    burn_rate: float
    remaining_cash: float
    runway_months: float


class ExpenseItem(BaseModel):
    name: str
    value: float


class RiskTrendPoint(BaseModel):
    month: str
    risk_score: float
    risk_level: str


class LoanReadinessPoint(BaseModel):
    month: str
    loan_score: float


class DashboardCharts(BaseModel):
    revenue_waterfall: RevenueWaterfall
    variance_chart: List[VarianceItem]
    rolling_trend: List[TrendPoint]
    burn_rate_chart: List[BurnRatePoint]
    expense_breakdown: List[ExpenseItem]
    risk_trend: List[RiskTrendPoint]
    loan_readiness: List[LoanReadinessPoint]


class InsightRequest(BaseModel):
    analysis_id: str
    chart_data: DashboardCharts


class FinancialInsight(BaseModel):
    title: str
    description: str
    severity: str  # low, medium, high


class InsightResponse(BaseModel):
    top_insights: List[str]
    risks: List[FinancialInsight]
    recommendations: List[str]
    generated_by: str


# =====================================================================
# Helper Functions
# =====================================================================

def _extract_financial_data(report_data: Dict[str, Any]) -> Dict[str, Any]:
    """Extract financial metrics from the structured agent report sections."""
    section1 = report_data.get("section_1_financial_health", {})
    section2 = report_data.get("section_2_cash_flow_forecast", {})
    section3 = report_data.get("section_3_risk_alerts", {})
    section6 = report_data.get("section_6_recommended_actions", {})

    # FinancialAnalyzer stores totals in a nested financial_health dict
    fh = section1.get("financial_health", {})
    cf = section1.get("cashflow_forecast", {})

    revenue = float(
        fh.get("total_revenue")
        or section1.get("revenue", {}).get("total")
        or 0
    )
    expenses = float(
        fh.get("total_expenses")
        or section1.get("expenses", {}).get("total")
        or 0
    )

    if revenue == 0 and expenses == 0:
        revenue = 100000
        expenses = 80000

    net_profit = revenue - expenses
    profit_margin = (net_profit / revenue * 100) if revenue > 0 else 0

    cash_balance = float(
        section1.get("cash_and_cash_equivalents")
        or section2.get("current_cash_position")
        or revenue * 0.15
    )

    monthly_burn_rate = float(
        section2.get("monthly_burn_rate")
        or cf.get("monthly_burn_rate")
        or (expenses / 12 if expenses > 0 else 0)
    )

    runway_months = float(
        section2.get("runway_months")
        or cf.get("runway_months")
        or (cash_balance / monthly_burn_rate if monthly_burn_rate > 0 else 0)
    )

    # Annual revenue growth rate from cashflow forecast trends
    revenue_growth_rate = float(
        (section2.get("trends") or {}).get("revenue_growth_rate") or 21.6
    )

    # Real category-level breakdowns produced by the FinancialAnalyzer
    expense_breakdown_raw = section1.get("expenses", {}).get("breakdown", [])
    revenue_breakdown_raw = section1.get("revenue", {}).get("breakdown", [])

    # Risk score from RiskDetector (0-100)
    risk_score = float(section3.get("risk_score") or 45)

    # Loan readiness score from ExplainabilityAgent
    loan_readiness_score = float(
        section6.get("loan_readiness_score")
        or report_data.get("section_5_loan_readiness_score")
        or 0
    )

    return {
        "revenue": revenue,
        "expenses": expenses,
        "net_profit": net_profit,
        "profit_margin": profit_margin,
        "monthly_burn_rate": monthly_burn_rate,
        "runway_months": runway_months,
        "cash_balance": cash_balance,
        "revenue_growth_rate": revenue_growth_rate,
        "expense_breakdown_raw": expense_breakdown_raw,
        "revenue_breakdown_raw": revenue_breakdown_raw,
        "risk_score": risk_score,
        "loan_readiness_score": loan_readiness_score,
    }


def _generate_revenue_waterfall(financial_data: Dict[str, Any]) -> RevenueWaterfall:
    """Generate revenue waterfall chart data from real breakdown or proportional fallback."""
    revenue = financial_data.get("revenue", 100000)
    revenue_breakdown_raw = financial_data.get("revenue_breakdown_raw", [])

    POSITIVE_COLORS = ["#10b981", "#34d399", "#6ee7b7", "#059669", "#047857"]
    NEGATIVE_COLOR = "#f87171"

    if revenue_breakdown_raw:
        items = []
        for i, item in enumerate(revenue_breakdown_raw):
            val = float(item.get("amount") or 0)
            color = NEGATIVE_COLOR if val < 0 else POSITIVE_COLORS[i % len(POSITIVE_COLORS)]
            items.append(WaterfallItem(
                name=str(item.get("category", f"Item {i + 1}")),
                value=round(val, 2),
                itemStyle={"color": color},
            ))
        items.append(WaterfallItem(name="Total Revenue", value=round(revenue, 2), itemStyle={"color": "#10b981"}))
    else:
        starting_base = revenue * 0.60
        new_customers = revenue * 0.28
        expansion = revenue * 0.15
        churn = -revenue * 0.08
        discounts = -revenue * 0.05
        items = [
            WaterfallItem(name="Starting Base", value=starting_base, itemStyle={"color": "#10b981"}),
            WaterfallItem(name="New Customers", value=new_customers, itemStyle={"color": "#34d399"}),
            WaterfallItem(name="Expansion", value=expansion, itemStyle={"color": "#6ee7b7"}),
            WaterfallItem(name="Churn", value=churn, itemStyle={"color": "#f87171"}),
            WaterfallItem(name="Discounts", value=discounts, itemStyle={"color": "#fb7185"}),
            WaterfallItem(name="Ending Revenue", value=revenue, itemStyle={"color": "#10b981"}),
        ]

    return RevenueWaterfall(items=items, total=revenue)


def _generate_variance_analysis(financial_data: Dict[str, Any]) -> List[VarianceItem]:
    """Generate budget vs actual variance using real expense breakdown when available."""
    revenue = financial_data.get("revenue", 100000)
    expenses = financial_data.get("expenses", 80000)
    expense_breakdown_raw = financial_data.get("expense_breakdown_raw", [])

    if revenue == 0:
        revenue = 100000
    if expenses == 0:
        expenses = 80000

    # Revenue row is always first
    items = [
        VarianceItem(
            category="Revenue",
            budget=round(revenue * 0.95, 2),
            actual=round(revenue, 2),
            variance_percent=round(((revenue - revenue * 0.95) / (revenue * 0.95)) * 100, 2),
        )
    ]

    if expense_breakdown_raw:
        # Use real category actuals; derive budget as 90% of actual (conservative plan)
        for item in expense_breakdown_raw[:4]:
            actual = float(item.get("amount") or 0)
            if actual <= 0:
                continue
            budget = round(actual * 0.90, 2)
            variance_pct = round(((actual - budget) / budget) * 100, 2) if budget > 0 else 0
            items.append(VarianceItem(
                category=str(item.get("category", "Expense")),
                budget=budget,
                actual=round(actual, 2),
                variance_percent=variance_pct,
            ))
    else:
        items += [
            VarianceItem(
                category="COGS",
                budget=round(revenue * 0.30, 2),
                actual=round(expenses * 0.30, 2),
                variance_percent=round(((expenses * 0.30 - revenue * 0.30) / (revenue * 0.30)) * 100, 2) if revenue * 0.30 > 0 else 0,
            ),
            VarianceItem(
                category="Marketing",
                budget=round(revenue * 0.12, 2),
                actual=round(expenses * 0.20, 2),
                variance_percent=round(((expenses * 0.20 - revenue * 0.12) / (revenue * 0.12)) * 100, 2) if revenue * 0.12 > 0 else 0,
            ),
            VarianceItem(
                category="Operations",
                budget=round(revenue * 0.18, 2),
                actual=round(expenses * 0.25, 2),
                variance_percent=round(((expenses * 0.25 - revenue * 0.18) / (revenue * 0.18)) * 100, 2) if revenue * 0.18 > 0 else 0,
            ),
            VarianceItem(
                category="R&D",
                budget=round(revenue * 0.10, 2),
                actual=round(expenses * 0.15, 2),
                variance_percent=round(((expenses * 0.15 - revenue * 0.10) / (revenue * 0.10)) * 100, 2) if revenue * 0.10 > 0 else 0,
            ),
        ]

    return items


def _generate_rolling_trend(financial_data: Dict[str, Any]) -> List[TrendPoint]:
    """Generate 12-month rolling revenue trend using real annual growth rate."""
    revenue = financial_data.get("revenue", 100000)
    # Annual growth rate (%) from cashflow forecast; convert to monthly
    annual_growth_rate = financial_data.get("revenue_growth_rate", 21.6)
    monthly_growth_pct = annual_growth_rate / 12.0

    if revenue == 0:
        revenue = 100000

    # Monthly revenue estimate for the most recent month
    monthly_revenue_now = revenue / 12.0

    points = []
    base_date = datetime.now()
    for i in range(12):
        month_date = base_date - timedelta(days=30 * (11 - i))
        # Back-calculate: current month is index 11, so months ago = 11 - i
        months_ago = 11 - i
        growth_factor = 1 / ((1 + monthly_growth_pct / 100) ** months_ago)
        value = monthly_revenue_now * growth_factor

        points.append(TrendPoint(
            month=month_date.strftime("%b %Y"),
            value=round(value, 2),
        ))

    return points


def _generate_burn_rate_chart(analysis_id: str, db: Session, current_user_id: str, financial_data: Dict[str, Any]) -> List[BurnRatePoint]:
    """Generate burn rate vs runway chart from real analysis history."""
    # Query all completed analyses for this user, sorted by created_at
    analyses = (
        db.query(models.Analysis)
        .filter(
            models.Analysis.user_id == current_user_id,
            models.Analysis.status == "completed",
        )
        .order_by(models.Analysis.created_at.asc())
        .all()
    )
    
    points = []
    
    if analyses:
        # Build trend from real historical data
        for analysis in analyses:
            report = db.query(models.Report).filter(models.Report.analysis_id == analysis.analysis_id).first()
            if not report or not report.report_data:
                continue
            
            section2 = report.report_data.get("section_2_cash_flow_forecast", {})
            monthly_burn = float(section2.get("monthly_burn_rate") or 0)
            runway = float(section2.get("runway_months") or 0)
            
            # Use report created_at as the month label
            month_label = analysis.created_at.strftime("%b %Y")
            
            # Calculate remaining cash based on burn rate and runway
            remaining = runway * monthly_burn if monthly_burn > 0 else 0
            
            points.append(BurnRatePoint(
                month=month_label,
                burn_rate=round(monthly_burn, 2),
                remaining_cash=round(remaining, 2),
                runway_months=round(runway, 1)
            ))
    else:
        # Fallback to current analysis data if no history
        monthly_burn = financial_data.get("monthly_burn_rate", 0)
        if monthly_burn == 0:
            monthly_burn = financial_data.get("expenses", 80000) / 12
        
        cash = financial_data.get("cash_balance", 0)
        if cash == 0:
            cash = financial_data.get("revenue", 100000) * 0.15
        
        runway = financial_data.get("runway_months", 0)
        if runway == 0 and monthly_burn > 0:
            runway = cash / monthly_burn
        
        points.append(BurnRatePoint(
            month=datetime.now().strftime("%b %Y"),
            burn_rate=round(monthly_burn, 2),
            remaining_cash=round(cash, 2),
            runway_months=round(max(0, runway), 1)
        ))
    
    return points


def _generate_expense_breakdown(financial_data: Dict[str, Any]) -> List[ExpenseItem]:
    """Generate expense breakdown using real category data when available."""
    expenses = financial_data.get("expenses", 80000)
    expense_breakdown_raw = financial_data.get("expense_breakdown_raw", [])

    if expense_breakdown_raw:
        items = [
            ExpenseItem(name=str(item.get("category", "Other")), value=round(float(item.get("amount") or 0), 2))
            for item in expense_breakdown_raw
            if float(item.get("amount") or 0) > 0
        ]
        if items:
            return items

    if expenses == 0:
        expenses = 80000

    return [
        ExpenseItem(name="Salaries", value=round(expenses * 0.45, 2)),
        ExpenseItem(name="Marketing", value=round(expenses * 0.20, 2)),
        ExpenseItem(name="Infrastructure", value=round(expenses * 0.15, 2)),
        ExpenseItem(name="Office", value=round(expenses * 0.12, 2)),
        ExpenseItem(name="Operations", value=round(expenses * 0.08, 2)),
    ]


def _generate_risk_trend(analysis_id: str, db: Session, current_user_id: str, report_data: Dict[str, Any]) -> List[RiskTrendPoint]:
    """Generate risk score trend from real analysis history."""
    # Query all completed analyses for this user, sorted by created_at
    analyses = (
        db.query(models.Analysis)
        .filter(
            models.Analysis.user_id == current_user_id,
            models.Analysis.status == "completed",
        )
        .order_by(models.Analysis.created_at.asc())
        .all()
    )
    
    points = []
    
    if analyses:
        # Build trend from real historical risk data
        for analysis in analyses:
            report = db.query(models.Report).filter(models.Report.analysis_id == analysis.analysis_id).first()
            if not report or not report.report_data:
                continue
            
            section3 = report.report_data.get("section_3_risk_alerts", {})
            risk_score = float(section3.get("risk_score") or 0)
            
            # Determine risk level
            if risk_score < 40:
                level = "Low"
            elif risk_score < 70:
                level = "Medium"
            else:
                level = "High"
            
            month_label = analysis.created_at.strftime("%b %Y")
            
            points.append(RiskTrendPoint(
                month=month_label,
                risk_score=round(risk_score, 1),
                risk_level=level
            ))
    else:
        # Fallback to current analysis risk score
        section3 = report_data.get("section_3_risk_alerts", {})
        overall_risk = float(section3.get("risk_score") or 45)
        
        if overall_risk < 40:
            level = "Low"
        elif overall_risk < 70:
            level = "Medium"
        else:
            level = "High"
        
        points.append(RiskTrendPoint(
            month=datetime.now().strftime("%b %Y"),
            risk_score=round(overall_risk, 1),
            risk_level=level
        ))
    
    return points


def _generate_loan_readiness(analysis_id: str, db: Session, current_user_id: str, financial_data: Dict[str, Any]) -> List[LoanReadinessPoint]:
    """Generate loan readiness score trend from real analysis history."""
    # Query all completed analyses for this user, sorted by created_at
    analyses = (
        db.query(models.Analysis)
        .filter(
            models.Analysis.user_id == current_user_id,
            models.Analysis.status == "completed",
        )
        .order_by(models.Analysis.created_at.asc())
        .all()
    )
    
    points = []
    
    if analyses:
        # Build trend from real historical loan readiness data
        for analysis in analyses:
            report = db.query(models.Report).filter(models.Report.analysis_id == analysis.analysis_id).first()
            if not report or not report.report_data:
                continue
            
            section6 = report.report_data.get("section_6_recommended_actions", {})
            loan_score = float(
                section6.get("loan_readiness_score")
                or report.report_data.get("section_5_loan_readiness_score")
                or 0
            )
            
            month_label = analysis.created_at.strftime("%b %Y")
            
            points.append(LoanReadinessPoint(
                month=month_label,
                loan_score=round(max(0, min(100, loan_score)), 1)
            ))
    else:
        # Fallback to current analysis loan readiness score
        loan_score = financial_data.get("loan_readiness_score", 0)
        
        points.append(LoanReadinessPoint(
            month=datetime.now().strftime("%b %Y"),
            loan_score=round(max(0, min(100, loan_score)), 1)
        ))
    
    return points


# =====================================================================
# Endpoints
# =====================================================================

@router.get("/charts/{analysis_id}", response_model=DashboardCharts)
async def get_dashboard_charts(
    analysis_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Get all dashboard chart data for an analysis"""
    
    # Verify analysis ownership
    analysis = (
        db.query(models.Analysis)
        .filter(
            models.Analysis.analysis_id == analysis_id,
            models.Analysis.user_id == current_user.user_id,
        )
        .first()
    )
    
    if not analysis:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Analysis not found",
        )
    
    # Get report data
    report = db.query(models.Report).filter(models.Report.analysis_id == analysis_id).first()
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report not found for this analysis",
        )
    
    report_data = report.report_data or {}
    financial_data = _extract_financial_data(report_data)
    
    # Generate all chart data
    charts = DashboardCharts(
        revenue_waterfall=_generate_revenue_waterfall(financial_data),
        variance_chart=_generate_variance_analysis(financial_data),
        rolling_trend=_generate_rolling_trend(financial_data),
        burn_rate_chart=_generate_burn_rate_chart(analysis_id, db, current_user.user_id, financial_data),
        expense_breakdown=_generate_expense_breakdown(financial_data),
        risk_trend=_generate_risk_trend(analysis_id, db, current_user.user_id, report_data),
        loan_readiness=_generate_loan_readiness(analysis_id, db, current_user.user_id, financial_data),
    )
    
    logger.info(f"Dashboard charts generated for analysis {analysis_id}")
    return charts


@router.post("/insights", response_model=InsightResponse)
async def generate_dashboard_insights(
    request: InsightRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Generate AI insights for dashboard charts using Nova 2 Lite"""
    
    # Verify analysis ownership
    analysis = (
        db.query(models.Analysis)
        .filter(
            models.Analysis.analysis_id == request.analysis_id,
            models.Analysis.user_id == current_user.user_id,
        )
        .first()
    )
    
    if not analysis:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Analysis not found",
        )
    
    # Build comprehensive prompt for Nova
    chart_summary = f"""
Analyze the following financial dashboard data and provide actionable insights:

REVENUE ANALYSIS:
- Total Revenue: ${request.chart_data.revenue_waterfall.total:,.2f}
- Revenue Components: {json.dumps([{"name": item.name, "amount": item.value} for item in request.chart_data.revenue_waterfall.items])}

BUDGET VARIANCE (Budget vs Actual):
{json.dumps([{"category": item.category, "budget": item.budget, "actual": item.actual, "variance": item.variance_percent} for item in request.chart_data.variance_chart])}

CASH BURN & RUNWAY:
- Monthly Burn Rate: ${request.chart_data.burn_rate_chart[0].burn_rate:,.2f}
- Runway Months: {request.chart_data.burn_rate_chart[0].runway_months:.1f}
- Remaining Cash: ${request.chart_data.burn_rate_chart[0].remaining_cash:,.2f}

EXPENSE BREAKDOWN:
{json.dumps([{"category": item.name, "amount": item.value} for item in request.chart_data.expense_breakdown])}

FINANCIAL HEALTH INDICATORS:
- Current Risk Score: {request.chart_data.risk_trend[-1].risk_score:.1f}/100 ({request.chart_data.risk_trend[-1].risk_level})
- Loan Readiness Score: {request.chart_data.loan_readiness[-1].loan_score:.1f}/100

Based on this comprehensive financial data, provide insightful analysis in the following JSON format:
{{
    "top_insights": [
        "insight about revenue trends",
        "insight about expenses and burn",
        "insight about financial health"
    ],
    "risks": [
        {{"title": "risk title", "description": "detailed explanation", "severity": "high"}},
        {{"title": "risk title", "description": "detailed explanation", "severity": "medium"}},
        {{"title": "risk title", "description": "detailed explanation", "severity": "low"}}
    ],
    "recommendations": [
        "actionable recommendation 1",
        "actionable recommendation 2",
        "actionable recommendation 3"
    ]
}}

Focus on:
1. Revenue growth and sustainability
2. Burn rate and runway implications
3. Cost optimization opportunities
4. Risk mitigation strategies
5. Loan readiness and financing health
"""
    
    system_prompt = """You are an expert CFO and financial analyst reviewing company financial dashboards. 
Your role is to provide clear, data-driven insights that help executives understand their financial position.

Guidelines:
- Focus on actionable insights, not just observations
- Identify both strengths and weaknesses
- Prioritize risks by severity and impact
- Provide specific, implementable recommendations
- Be direct and concise in your analysis
- Always output valid JSON"""
    
    try:
        logger.info(f"Generating insights for analysis {request.analysis_id}")
        nova = NovaClient()
        
        result = nova.invoke_agent(
            prompt=chart_summary,
            system_prompt=system_prompt,
            temperature=0.3,  # Lower temperature for more consistent financial analysis
            max_tokens=2000,
        )
        
        logger.info(f"Nova response received: {result}")
        
        # Handle error responses from Nova
        if isinstance(result, dict) and "error" in result:
            logger.error(f"Nova error: {result['error']}")
            # Return default insights on error
            return InsightResponse(
                top_insights=[
                    "Analysis in progress. Data review recommended.",
                ],
                risks=[
                    FinancialInsight(
                        title="Incomplete Analysis",
                        description="AI analysis temporarily unavailable. Review financial metrics manually.",
                        severity="medium",
                    )
                ],
                recommendations=[
                    "Review expense structure manually",
                    "Monitor burn rate trends",
                    "Assess revenue sustainability"
                ],
                generated_by="Amazon Nova 2 Lite (Manual Fallback)",
            )
        
        # Extract insights data
        insights_data = result if isinstance(result, dict) else {}
        
        # Validate and extract top insights
        top_insights = insights_data.get("top_insights", [])
        if not isinstance(top_insights, list):
            top_insights = [str(top_insights)]
        top_insights = [str(i) for i in top_insights][:3]
        
        # Validate and extract risks
        risks_raw = insights_data.get("risks", [])
        if not isinstance(risks_raw, list):
            risks_raw = [risks_raw]
        
        risks = []
        for risk in risks_raw:
            if isinstance(risk, dict):
                risks.append(
                    FinancialInsight(
                        title=str(risk.get("title", "Unknown Risk")),
                        description=str(risk.get("description", "")),
                        severity=str(risk.get("severity", "medium")).lower(),
                    )
                )
        
        # Validate and extract recommendations
        recommendations = insights_data.get("recommendations", [])
        if not isinstance(recommendations, list):
            recommendations = [str(recommendations)]
        recommendations = [str(r) for r in recommendations][:3]
        
        return InsightResponse(
            top_insights=top_insights,
            risks=risks,
            recommendations=recommendations,
            generated_by="Amazon Nova 2 Lite",
        )
        
    except Exception as exc:
        logger.error(f"Failed to generate insights: {exc}", exc_info=True)
        # Return graceful fallback instead of error
        return InsightResponse(
            top_insights=[
                "Review financial trends in the charts above",
            ],
            risks=[
                FinancialInsight(
                    title="Analysis Unavailable",
                    description="Detailed AI analysis is temporarily unavailable. Please review the financial dashboards directly.",
                    severity="low",
                )
            ],
            recommendations=[
                "Review revenue trends",
                "Monitor expense growth",
                "Track runway metrics"
            ],
            generated_by="Amazon Nova 2 Lite (Fallback)",
        )
