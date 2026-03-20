"""
Technical Indicators & Confirmation
=====================================
Computes technical signals used for entry/exit confirmation:
  - EMA (various periods)
  - RSI (14-period)
  - MACD (12/26/9)
  - ATR (14-period) — used for position sizing and stops
  - Volume confirmation

All calculations use pandas/numpy (no external TA library dependency,
but compatible with the `ta` library if installed).
"""

import logging
from typing import Optional

import numpy as np
import pandas as pd

from config import TechnicalConfig, DEFAULT_CONFIG

logger = logging.getLogger(__name__)


class TechnicalAnalyzer:
    """Computes technical indicators for IDX stocks."""

    def __init__(self, config: TechnicalConfig = None):
        self.cfg = config or DEFAULT_CONFIG.technical

    def compute_all_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Add all technical indicator columns to the price DataFrame.

        Input df must have: open, high, low, close, volume (DatetimeIndex)
        Returns df with added columns for each indicator.
        """
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
            out["close"],
            self.cfg.macd_fast,
            self.cfg.macd_slow,
            self.cfg.macd_signal,
        )
        out["macd"] = macd
        out["macd_signal"] = signal
        out["macd_histogram"] = histogram

        # ATR
        out["atr"] = self._atr(out, period=14)

        # Volume average
        out["vol_avg_20"] = out["volume"].rolling(20, min_periods=5).mean()
        out["vol_ratio"] = out["volume"] / out["vol_avg_20"].replace(0, np.nan)

        return out

    def check_entry_conditions(self, row: pd.Series) -> bool:
        """
        Check if a single row passes ALL technical entry conditions.

        Conditions:
          1. Price > EMA(50)
          2. RSI between 40 and 70
          3. MACD histogram > 0 (MACD line above signal line)
          4. Volume ≥ 1.2 × 20-day average
        """
        try:
            # 1. Price above EMA
            if row["close"] <= row.get("ema_50", 0):
                return False

            # 2. RSI in range
            rsi = row.get("rsi", 50)
            if rsi < self.cfg.rsi_min or rsi > self.cfg.rsi_max:
                return False

            # 3. MACD positive
            if row.get("macd_histogram", 0) <= 0:
                return False

            # 4. Volume confirmation
            vol_ratio = row.get("vol_ratio", 1.0)
            if vol_ratio < self.cfg.entry_volume_multiplier:
                return False

            return True

        except Exception as e:
            logger.debug(f"Technical check error: {e}")
            return False

    # ──────────────────────────────────────────────────────────
    # Indicator calculations (pure pandas/numpy)
    # ──────────────────────────────────────────────────────────

    @staticmethod
    def _ema(series: pd.Series, period: int) -> pd.Series:
        """Exponential Moving Average."""
        return series.ewm(span=period, adjust=False).mean()

    @staticmethod
    def _rsi(series: pd.Series, period: int = 14) -> pd.Series:
        """
        Relative Strength Index using Wilder's smoothing method.
        """
        delta = series.diff()
        gain = delta.where(delta > 0, 0.0)
        loss = (-delta).where(delta < 0, 0.0)

        # Use Wilder's smoothing (equivalent to EMA with alpha = 1/period)
        avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()

        rs = avg_gain / avg_loss.replace(0, np.nan)
        rsi = 100 - (100 / (1 + rs))
        return rsi.fillna(50)

    @staticmethod
    def _macd(
        series: pd.Series,
        fast: int = 12,
        slow: int = 26,
        signal_period: int = 9,
    ):
        """
        MACD (Moving Average Convergence Divergence).
        Returns: (macd_line, signal_line, histogram)
        """
        ema_fast = series.ewm(span=fast, adjust=False).mean()
        ema_slow = series.ewm(span=slow, adjust=False).mean()
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=signal_period, adjust=False).mean()
        histogram = macd_line - signal_line
        return macd_line, signal_line, histogram

    @staticmethod
    def _atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
        """
        Average True Range.
        True Range = max(H-L, |H-Cprev|, |L-Cprev|)
        ATR = Wilder's smoothed average of TR.
        """
        high = df["high"]
        low = df["low"]
        prev_close = df["close"].shift(1)

        tr1 = high - low
        tr2 = (high - prev_close).abs()
        tr3 = (low - prev_close).abs()

        true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = true_range.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
        return atr
