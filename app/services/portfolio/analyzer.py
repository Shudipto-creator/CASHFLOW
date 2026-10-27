"""
Portfolio risk metrics inspired by TrueWealth-AI portfolio_analyst_agent.

Numbers are computed with pandas/numpy (and optional yfinance price history).
The LLM only explains the math — it never invents risk figures.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

CONCENTRATION_THRESHOLD_PCT = 40.0
DEFAULT_HISTORY_PERIOD = "6mo"


def parse_holdings_text(text: str) -> List[Dict[str, Any]]:
    """Parse strings like '10 shares of AAPL, 5 MSFT @ 400' into holdings."""
    holdings: List[Dict[str, Any]] = []
    if not text:
        return holdings

    pattern = re.compile(
        r"(?P<shares>\d+(?:\.\d+)?)\s*(?:shares?\s+of\s+)?(?P<symbol>[A-Za-z.]{1,10})"
        r"(?:\s*[@x]\s*(?P<price>\d+(?:\.\d+)?))?",
        re.IGNORECASE,
    )
    for match in pattern.finditer(text):
        holdings.append(
            {
                "symbol": match.group("symbol").upper(),
                "shares": float(match.group("shares")),
                "price": float(match.group("price")) if match.group("price") else None,
            }
        )
    return holdings


class PortfolioAnalyzer:
    """Compute allocation, annualized volatility, max drawdown, concentration."""

    def __init__(self, concentration_threshold_pct: float = CONCENTRATION_THRESHOLD_PCT):
        self.concentration_threshold_pct = concentration_threshold_pct

    def analyze(
        self,
        holdings: List[Dict[str, Any]],
        history_period: str = DEFAULT_HISTORY_PERIOD,
        price_history: Optional[pd.DataFrame] = None,
    ) -> Dict[str, Any]:
        if not holdings:
            return {
                "status": "empty",
                "message": "No holdings provided",
                "metrics": {},
                "positions": [],
            }

        normalized = []
        for h in holdings:
            symbol = str(h.get("symbol", "")).upper().strip()
            shares = float(h.get("shares", 0) or 0)
            if not symbol or shares <= 0:
                continue
            normalized.append(
                {
                    "symbol": symbol,
                    "shares": shares,
                    "price": float(h["price"]) if h.get("price") is not None else None,
                }
            )

        if not normalized:
            return {
                "status": "empty",
                "message": "No valid holdings",
                "metrics": {},
                "positions": [],
            }

        prices, source = self._resolve_prices(normalized, history_period, price_history)
        positions = []
        for h in normalized:
            px = prices.get(h["symbol"])
            if px is None:
                continue
            value = h["shares"] * px
            positions.append(
                {
                    "symbol": h["symbol"],
                    "shares": h["shares"],
                    "price": round(px, 4),
                    "value": round(value, 2),
                }
            )

        total_value = sum(p["value"] for p in positions) or 1.0
        for p in positions:
            p["allocation_pct"] = round(100.0 * p["value"] / total_value, 2)

        positions.sort(key=lambda p: p["value"], reverse=True)
        top = positions[0] if positions else None
        concentration_flag = bool(
            top and top["allocation_pct"] >= self.concentration_threshold_pct
        )

        vol, max_dd, series_note = self._risk_from_history(
            positions, history_period, price_history
        )

        metrics = {
            "total_value": round(sum(p["value"] for p in positions), 2),
            "position_count": len(positions),
            "annualized_volatility_pct": vol,
            "max_drawdown_pct": max_dd,
            "top_holding": top["symbol"] if top else None,
            "top_allocation_pct": top["allocation_pct"] if top else None,
            "concentration_risk": concentration_flag,
            "concentration_threshold_pct": self.concentration_threshold_pct,
            "price_source": source,
            "history_note": series_note,
        }

        return {
            "status": "ok",
            "positions": positions,
            "metrics": metrics,
            "advisor_notes": self._notes(metrics, positions),
            "privacy": "Metrics computed locally with pandas/numpy; LLM should only explain these numbers.",
        }

    def analyze_from_text(self, text: str, history_period: str = DEFAULT_HISTORY_PERIOD) -> Dict[str, Any]:
        return self.analyze(parse_holdings_text(text), history_period=history_period)

    def _resolve_prices(
        self,
        holdings: List[Dict[str, Any]],
        history_period: str,
        price_history: Optional[pd.DataFrame],
    ) -> Tuple[Dict[str, float], str]:
        prices: Dict[str, float] = {}
        for h in holdings:
            if h.get("price") is not None:
                prices[h["symbol"]] = float(h["price"])

        missing = [h["symbol"] for h in holdings if h["symbol"] not in prices]
        if not missing:
            return prices, "provided"

        # Prefer explicit history frame last close
        if price_history is not None and not price_history.empty:
            for sym in missing:
                if sym in price_history.columns:
                    series = price_history[sym].dropna()
                    if len(series):
                        prices[sym] = float(series.iloc[-1])
            missing = [s for s in missing if s not in prices]
            if not missing:
                return prices, "price_history"

        # Optional live fetch
        try:
            import yfinance as yf  # type: ignore

            data = yf.download(
                missing,
                period=history_period,
                progress=False,
                auto_adjust=True,
            )
            close = data["Close"] if "Close" in data.columns else data
            if isinstance(close, pd.Series):
                close = close.to_frame(missing[0])
            for sym in missing:
                if sym in close.columns:
                    series = close[sym].dropna()
                    if len(series):
                        prices[sym] = float(series.iloc[-1])
            return prices, "yfinance"
        except Exception as exc:
            logger.warning("yfinance unavailable or failed (%s); using fallback prices", exc)
            for sym in missing:
                prices.setdefault(sym, 100.0)
            return prices, "fallback"

    def _risk_from_history(
        self,
        positions: List[Dict[str, Any]],
        history_period: str,
        price_history: Optional[pd.DataFrame],
    ) -> Tuple[Optional[float], Optional[float], str]:
        symbols = [p["symbol"] for p in positions]
        weights = np.array([p["value"] for p in positions], dtype=float)
        if weights.sum() == 0:
            return None, None, "no_value"
        weights = weights / weights.sum()

        hist = price_history
        if hist is None:
            try:
                import yfinance as yf  # type: ignore

                data = yf.download(
                    symbols,
                    period=history_period,
                    progress=False,
                    auto_adjust=True,
                )
                hist = data["Close"] if "Close" in data.columns else data
                if isinstance(hist, pd.Series):
                    hist = hist.to_frame(symbols[0])
            except Exception as exc:
                logger.info("Skipping live history for risk metrics: %s", exc)
                return None, None, "history_unavailable"

        if hist is None or hist.empty:
            return None, None, "history_unavailable"

        cols = [s for s in symbols if s in hist.columns]
        if not cols:
            return None, None, "symbols_missing_from_history"

        aligned_weights = []
        frame = hist[cols].dropna(how="all").ffill().dropna()
        for s in cols:
            idx = symbols.index(s)
            aligned_weights.append(weights[idx])
        w = np.array(aligned_weights, dtype=float)
        w = w / w.sum()

        returns = frame.pct_change().dropna()
        if returns.empty:
            return None, None, "insufficient_history"

        port_returns = returns.values @ w
        ann_vol = float(np.std(port_returns, ddof=1) * np.sqrt(252) * 100)
        cumulative = np.cumprod(1 + port_returns)
        peak = np.maximum.accumulate(cumulative)
        drawdown = (cumulative - peak) / peak
        max_dd = float(drawdown.min() * 100)

        return round(ann_vol, 2), round(max_dd, 2), f"computed_over_{history_period}"

    @staticmethod
    def _notes(metrics: Dict[str, Any], positions: List[Dict[str, Any]]) -> List[str]:
        notes = []
        if metrics.get("concentration_risk"):
            notes.append(
                f"Concentration risk: {metrics.get('top_holding')} is "
                f"{metrics.get('top_allocation_pct')}% of the portfolio "
                f"(threshold {metrics.get('concentration_threshold_pct')}%)."
            )
        if metrics.get("annualized_volatility_pct") is not None:
            notes.append(
                f"Annualized volatility is {metrics['annualized_volatility_pct']}% "
                f"with max drawdown {metrics.get('max_drawdown_pct')}%."
            )
        if positions:
            alloc = ", ".join(f"{p['symbol']} {p['allocation_pct']}%" for p in positions[:5])
            notes.append(f"Allocation: {alloc}.")
        return notes
