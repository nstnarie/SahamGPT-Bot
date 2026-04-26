"""
Technical Indicators v4
========================
Computes indicators for breakout detection + confirmation.
"""

import logging
import numpy as np
import pandas as pd

from config import TechnicalConfig, DEFAULT_CONFIG

logger = logging.getLogger(__name__)


class TechnicalAnalyzer:
    """Computes technical indicators for IDX stocks."""

    def __init__(self, config: TechnicalConfig = None):
        self.cfg = config or DEFAULT_CONFIG.technical

    def compute_all_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add all indicator columns to the price DataFrame."""
        if df.empty or len(df) < 30:
            logger.warning("Insufficient data for indicator calculation")
            return df

        out = df.copy()

        # EMAs
        out["ema_20"] = self._ema(out["close"], 20)
        out["ema_50"] = self._ema(out["close"], 50)
        out["ema_200"] = self._ema(out["close"], 200)

        # RSI
        out["rsi"] = self._rsi(out["close"], self.cfg.rsi_period)

        # MACD
        macd, signal, histogram = self._macd(
            out["close"], self.cfg.macd_fast, self.cfg.macd_slow, self.cfg.macd_signal,
        )
        out["macd"] = macd
        out["macd_signal"] = signal
        out["macd_histogram"] = histogram

        # ATR
        out["atr"] = self._atr(out, period=14)

        # Volume
        out["vol_avg_20"] = out["volume"].rolling(20, min_periods=5).mean()
        out["vol_ratio"] = out["volume"] / out["vol_avg_20"].replace(0, np.nan)
        out["avg_daily_value_20d"] = (out["close"] * out["volume"]).rolling(20, min_periods=5).mean()

        # 52-week (252 trading days) high for entry quality filter
        out["high_252d"] = out["high"].rolling(window=252, min_periods=60).max()
        out["dist_from_52w_high"] = (out["close"] / out["high_252d"] - 1) * 100

        # Step 7 ranking features
        out["price_vs_ma200"] = (out["close"] / out["ema_200"] - 1) * 100
        out["atr_pct"] = out["atr"] / out["close"] * 100
        out["prior_return_5d"] = (out["close"] / out["close"].shift(5) - 1) * 100

        return out

    def check_entry_conditions(self, row: pd.Series) -> bool:
        """Kept for backward compatibility. v4 uses breakout logic instead."""
        try:
            if row["close"] <= row.get("ema_50", 0):
                return False
            rsi = row.get("rsi", 50)
            if rsi < self.cfg.rsi_min or rsi > self.cfg.rsi_max:
                return False
            if row.get("macd_histogram", 0) <= 0:
                return False
            vol_ratio = row.get("vol_ratio", 1.0)
            if vol_ratio < self.cfg.entry_volume_multiplier:
                return False
            return True
        except Exception:
            return False

    @staticmethod
    def _ema(series: pd.Series, period: int) -> pd.Series:
        return series.ewm(span=period, adjust=False).mean()

    @staticmethod
    def _rsi(series: pd.Series, period: int = 14) -> pd.Series:
        delta = series.diff()
        gain = delta.where(delta > 0, 0.0)
        loss = (-delta).where(delta < 0, 0.0)
        avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
        rs = avg_gain / avg_loss.replace(0, np.nan)
        rsi = 100 - (100 / (1 + rs))
        return rsi.fillna(50)

    @staticmethod
    def _macd(series, fast=12, slow=26, signal_period=9):
        ema_fast = series.ewm(span=fast, adjust=False).mean()
        ema_slow = series.ewm(span=slow, adjust=False).mean()
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=signal_period, adjust=False).mean()
        histogram = macd_line - signal_line
        return macd_line, signal_line, histogram

    @staticmethod
    def _atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
        high, low = df["high"], df["low"]
        prev_close = df["close"].shift(1)
        tr1 = high - low
        tr2 = (high - prev_close).abs()
        tr3 = (low - prev_close).abs()
        true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        return true_range.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
