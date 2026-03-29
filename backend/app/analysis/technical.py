"""Technical analysis engine — computes RSI, MACD, Bollinger Bands, SMA, EMA."""

import logging
from datetime import datetime
from typing import Optional

import pandas as pd

from app.models.db import get_session, IndexHistoryModel
from app.models.schemas import AnalysisResult

logger = logging.getLogger(__name__)

# ── Indicator Config ────────────────────────────────────────────


INDICATOR_CONFIG = {
    "SMA_20": {"period": 20, "indicator": "sma"},
    "SMA_50": {"period": 50, "indicator": "sma"},
    "EMA_12": {"period": 12, "indicator": "ema"},
    "EMA_26": {"period": 26, "indicator": "ema"},
    "RSI_14": {"period": 14, "indicator": "rsi"},
    "MACD_12_26_9": {"indicator": "macd"},
    "BB_20_2": {"period": 20, "indicator": "bb"},
}


# ── TechnicalAnalyzer ────────────────────────────────────────────


class TechnicalAnalyzer:
    """Computes technical indicators and generates trading signals."""

    def __init__(self):
        self._db = get_session()

    def _get_history_df(self, symbol: str, period: str = "3mo") -> pd.DataFrame:
        """Load history from DB as DataFrame."""
        points = (
            self._db.query(IndexHistoryModel)
            .filter(IndexHistoryModel.symbol == symbol)
            .order_by(IndexHistoryModel.date.desc())
            .limit(200)
            .all()
        )

        if not points:
            return pd.DataFrame()

        df = pd.DataFrame(
            [
                {
                    "date": p.date,
                    "open": p.open_price,
                    "high": p.high,
                    "low": p.low,
                    "close": p.close,
                    "volume": p.volume,
                }
                for p in points
            ]
        )
        df = df.sort_values("date")
        return df

    def _compute_indicators(self, df: pd.DataFrame) -> dict:
        """Compute technical indicators on OHLCV data."""
        indicators = {}

        if df.empty or len(df) < 50:
            return indicators

        close = df["close"]

        # Simple Moving Averages
        for period in [20, 50]:
            if len(df) >= period:
                sma = close.rolling(window=period).mean().iloc[-1]
                indicators[f"sma_{period}"] = round(float(sma), 4)

        # Exponential Moving Averages
        for period in [12, 26]:
            if len(df) >= period:
                ema = close.ewm(span=period, adjust=False).mean().iloc[-1]
                indicators[f"ema_{period}"] = round(float(ema), 4)

        # RSI (Relative Strength Index)
        if len(df) >= 14:
            delta = close.diff()
            gain = delta.where(delta > 0, 0.0)
            loss = (-delta).where(delta < 0, 0.0)
            avg_gain = gain.rolling(window=14).mean()
            avg_loss = loss.rolling(window=14).mean()
            rs = avg_gain / avg_loss
            rsi = 100 - (100 / (1 + rs))
            indicators["rsi_14"] = round(float(rsi.iloc[-1]), 4)

        # MACD (Moving Average Convergence Divergence)
        if len(df) >= 26:
            ema_12 = close.ewm(span=12, adjust=False).mean()
            ema_26 = close.ewm(span=26, adjust=False).mean()
            macd_line = ema_12 - ema_26
            signal_line = macd_line.ewm(span=9, adjust=False).mean()
            macd_hist = macd_line - signal_line
            indicators["macd"] = round(float(macd_line.iloc[-1]), 4)
            indicators["macd_signal"] = round(float(signal_line.iloc[-1]), 4)
            indicators["macd_hist"] = round(float(macd_hist.iloc[-1]), 4)

        # Bollinger Bands
        if len(df) >= 20:
            sma_20 = close.rolling(window=20).mean()
            std_20 = close.rolling(window=20).std()
            bb_upper = sma_20 + (2 * std_20)
            bb_lower = sma_20 - (2 * std_20)
            indicators["bb_upper"] = round(float(bb_upper.iloc[-1]), 4)
            indicators["bb_middle"] = round(float(sma_20.iloc[-1]), 4)
            indicators["bb_lower"] = round(float(bb_lower.iloc[-1]), 4)

            # %B (position within bands)
            if indicators["bb_upper"] != indicators["bb_lower"]:
                indicators["bb_percent"] = round(
                    float((close.iloc[-1] - indicators["bb_lower"]) /
                          (indicators["bb_upper"] - indicators["bb_lower"])), 4
                )

        return indicators

    def _generate_signal(self, indicators: dict, price: float) -> tuple[str, str, float]:
        """Generate trend, recommendation and confidence from indicators."""
        signals = []
        weights = []

        # RSI
        if "rsi_14" in indicators:
            rsi = indicators["rsi_14"]
            if rsi < 30:
                signals.append(("oversold", "buy", 0.7))
            elif rsi > 70:
                signals.append(("overbought", "sell", 0.7))
            else:
                signals.append(("neutral_rsi", "hold", 0.3))

        # MACD
        if "macd" in indicators and "macd_signal" in indicators:
            macd = indicators["macd"]
            signal = indicators["macd_signal"]
            hist = indicators.get("macd_hist", 0)
            if macd > signal and hist > 0:
                signals.append(("bullish_macd", "buy", 0.6))
            elif macd < signal and hist < 0:
                signals.append(("bearish_macd", "sell", 0.6))
            else:
                signals.append(("neutral_macd", "hold", 0.3))

        # Moving Average Crossover
        if "sma_20" in indicators and "sma_50" in indicators:
            sma_20 = indicators["sma_20"]
            sma_50 = indicators["sma_50"]
            if sma_20 > sma_50:
                signals.append(("above_sma_50", "buy", 0.5))
            else:
                signals.append(("below_sma_50", "sell", 0.5))

        # Bollinger Bands
        if "bb_percent" in indicators:
            bb_pct = indicators["bb_percent"]
            if bb_pct < 0.2:
                signals.append(("bb_oversold", "buy", 0.5))
            elif bb_pct > 0.8:
                signals.append(("bb_overbought", "sell", 0.5))

        if not signals:
            return "neutral", "hold", 0.0

        # Aggregate signals
        buy_signals = [s for s in signals if s[1] == "buy"]
        sell_signals = [s for s in signals if s[1] == "sell"]

        if len(buy_signals) > len(sell_signals):
            trend = "upward"
            recommendation = "buy"
            confidence = sum(s[2] for s in buy_signals) / len(buy_signals)
        elif len(sell_signals) > len(buy_signals):
            trend = "downward"
            recommendation = "sell"
            confidence = sum(s[2] for s in sell_signals) / len(sell_signals)
        else:
            trend = "neutral"
            recommendation = "hold"
            confidence = 0.3

        confidence = min(max(confidence, 0.0), 1.0)
        return trend, recommendation, confidence

    async def analyze(self, symbol: str, period: str = "3mo") -> AnalysisResult:
        """Run full technical analysis on an index."""
        df = self._get_history_df(symbol, period)

        if df.empty:
            # Return a "no data" result
            return AnalysisResult(
                symbol=symbol,
                timestamp=datetime.utcnow(),
                trend="unknown",
                recommendation="hold",
                confidence=0.0,
                indicators={},
                notes="No historical data available for analysis. Data pipeline may not have fetched yet.",
            )

        indicators = self._compute_indicators(df)
        current_price = float(df["close"].iloc[-1])
        trend, recommendation, confidence = self._generate_signal(indicators, current_price)

        # Build notes
        notes_parts = []
        if "rsi_14" in indicators:
            notes_parts.append(f"RSI(14)={indicators['rsi_14']:.1f}")
        if "macd" in indicators:
            notes_parts.append(f"MACD={indicators['macd']:.2f}")
        notes = f"Price={current_price:.2f}. {'; '.join(notes_parts)}" if notes_parts else None

        return AnalysisResult(
            symbol=symbol,
            timestamp=datetime.utcnow(),
            trend=trend,
            recommendation=recommendation,
            confidence=confidence,
            indicators=indicators,
            notes=notes,
        )
