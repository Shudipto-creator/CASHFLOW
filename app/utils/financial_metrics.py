"""Financial metrics calculation utilities"""

from typing import List, Dict, Any
from datetime import datetime, timedelta
from collections import defaultdict
import re


def calculate_burn_rate(expenses: List[Dict], time_period_days: int) -> float:
    """
    Calculate average daily/monthly cash burn

    Args:
        expenses: List of expense transactions with amount and date
        time_period_days: Time period in days

    Returns:
        Burn rate as float
    """
    if not expenses or time_period_days <= 0:
        return 0.0

    total_expenses = sum(exp.get("amount", 0) for exp in expenses)
    daily_burn = total_expenses / time_period_days
    return round(daily_burn, 2)


def calculate_runway(current_cash: float, monthly_burn: float) -> float:
    """
    Calculate months until cash depletes

    Args:
        current_cash: Current cash balance
        monthly_burn: Monthly burn rate

    Returns:
        Runway in months
    """
    if monthly_burn <= 0:
        return float("inf")

    if current_cash <= 0:
        return 0.0

    runway_months = current_cash / monthly_burn
    return round(runway_months, 1)


def calculate_debt_to_income(total_debt: float, monthly_income: float) -> float:
    """
    Calculate debt-to-income ratio

    Args:
        total_debt: Total debt amount
        monthly_income: Monthly income

    Returns:
        Ratio as percentage
    """
    if monthly_income <= 0:
        return 0.0

    ratio = (total_debt / monthly_income) * 100
    return round(ratio, 2)


def calculate_liquidity_ratio(current_assets: float, current_liabilities: float) -> float:
    """
    Calculate liquidity/current ratio

    Args:
        current_assets: Current assets
        current_liabilities: Current liabilities

    Returns:
        Ratio as float
    """
    if current_liabilities <= 0:
        return 0.0

    ratio = current_assets / current_liabilities
    return round(ratio, 2)


def categorize_transaction(description: str, amount: float) -> str:
    """
    Use simple rule-based categorization

    Args:
        description: Transaction description
        amount: Transaction amount

    Returns:
        Category string
    """
    description_lower = description.lower()

    # Define category keywords
    categories = {
        "salary": ["salary", "payroll", "wage", "compensation"],
        "rent": ["rent", "lease", "rental"],
        "utilities": ["electricity", "water", "gas", "utility", "internet", "phone"],
        "marketing": ["marketing", "advertising", "ads", "promotion", "social media"],
        "loan_emi": ["emi", "loan", "installment", "repayment"],
        "tax": ["tax", "gst", "income tax", "tds", "vat"],
        "revenue": ["revenue", "sales", "income", "payment received", "invoice"],
    }

    # Check for matches
    for category, keywords in categories.items():
        if any(keyword in description_lower for keyword in keywords):
            return category

    # Default categorization based on amount
    if amount < 0:
        return "expense"
    else:
        return "revenue"


def detect_recurring_payments(transactions: List[Dict]) -> List[Dict]:
    """
    Identify recurring payments by amount and frequency patterns

    Args:
        transactions: List of transaction dicts with amount, date, description

    Returns:
        List of detected recurring payments with frequency
    """
    if not transactions:
        return []

    # Group by similar amounts (within 5% tolerance)
    amount_groups = defaultdict(list)

    for trans in transactions:
        amount = abs(trans.get("amount", 0))
        if amount == 0:
            continue

        # Find matching group
        matched = False
        for base_amount in amount_groups.keys():
            if abs(amount - base_amount) / base_amount < 0.05:  # 5% tolerance
                amount_groups[base_amount].append(trans)
                matched = True
                break

        if not matched:
            amount_groups[amount].append(trans)

    # Detect recurring patterns (3+ occurrences)
    recurring = []

    for base_amount, trans_list in amount_groups.items():
        if len(trans_list) < 3:
            continue

        # Sort by date
        sorted_trans = sorted(trans_list, key=lambda x: x.get("date", ""))

        # Calculate intervals between transactions
        intervals = []
        for i in range(1, len(sorted_trans)):
            try:
                date1 = datetime.fromisoformat(sorted_trans[i - 1].get("date", ""))
                date2 = datetime.fromisoformat(sorted_trans[i].get("date", ""))
                interval = (date2 - date1).days
                intervals.append(interval)
            except:
                continue

        if not intervals:
            continue

        # Check if intervals are consistent (within 7 days tolerance)
        avg_interval = sum(intervals) / len(intervals)

        is_consistent = all(abs(interval - avg_interval) <= 7 for interval in intervals)

        if is_consistent:
            # Determine frequency
            if 25 <= avg_interval <= 35:
                frequency = "monthly"
            elif 85 <= avg_interval <= 95:
                frequency = "quarterly"
            elif 350 <= avg_interval <= 380:
                frequency = "yearly"
            elif 12 <= avg_interval <= 17:
                frequency = "bi-weekly"
            elif 5 <= avg_interval <= 9:
                frequency = "weekly"
            else:
                frequency = f"every {int(avg_interval)} days"

            recurring.append({
                "description": trans_list[0].get("description", "Unknown"),
                "amount": round(base_amount, 2),
                "frequency": frequency,
                "occurrences": len(trans_list),
                "avg_interval_days": int(avg_interval)
            })

    return recurring


def calculate_growth_rate(values: List[float]) -> float:
    """
    Calculate simple growth rate from a list of values

    Args:
        values: List of values over time

    Returns:
        Growth rate as percentage
    """
    if len(values) < 2:
        return 0.0

    first_value = values[0]
    last_value = values[-1]

    if first_value == 0:
        return 0.0

    growth_rate = ((last_value - first_value) / first_value) * 100
    return round(growth_rate, 2)


def categorize_risk_level(score: int) -> str:
    """
    Categorize risk score into levels

    Args:
        score: Risk score 0-100

    Returns:
        Risk level string
    """
    if score <= 25:
        return "low"
    elif score <= 50:
        return "medium"
    elif score <= 75:
        return "high"
    else:
        return "critical"


def compute_loan_readiness_score(
    profit_margin: float = 0.0,
    runway_months: float = 0.0,
    burn_rate: float = 0.0,
    risk_score: float = 0.0
) -> int:
    """
    Compute deterministic loan readiness score using financial metrics.
    
    This function provides a fallback calculation that doesn't depend on LLM output,
    ensuring the loan readiness score is always computed and available.

    Args:
        profit_margin: Net profit margin as percentage (e.g., 5.0 for 5%)
        runway_months: Cash runway in months (e.g., 12.5)
        burn_rate: Monthly burn rate (not used in formula but available for logging)
        risk_score: Overall risk score 0-100 (higher = more risky)

    Returns:
        Loan readiness score as integer between 0-100
        
    Formula:
        score = max(0, min(100, int(50 + profit_margin*2 - risk_score*0.5 + runway_months*3)))
    """
    # Handle None/NaN values
    profit_margin = max(0, float(profit_margin or 0.0))
    runway_months = max(0, float(runway_months or 0.0))
    risk_score = max(0, min(100, float(risk_score or 0.0)))
    
    # Apply deterministic formula
    base_score = 50  # Base score
    profit_boost = profit_margin * 2  # Profitability increases score
    risk_penalty = risk_score * 0.5  # Risk decreases score
    runway_bonus = runway_months * 3  # Longer runway increases score
    
    raw_score = base_score + profit_boost - risk_penalty + runway_bonus
    
    # Clamp to 0-100 range
    loan_readiness_score = max(0, min(100, int(raw_score)))
    
    return loan_readiness_score
