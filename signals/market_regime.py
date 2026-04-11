"""
Market Regime Filter
=====================
Classifies the IHSG (Jakarta Composite Index) into:
  BULL     — trending up, broad participation
  BEAR     — trending down, weak breadth
  SIDEWAYS — mixed signals

Rules:
  BULL  : EMA20 > EMA50 > EMA200 on IHSG  AND  breadth > 60%
  BEAR  : EMA20 < EMA50 < EMA200 on IHSG  AND  breadth < 40%
  SIDEWAYS : everything else

Breadth = % of universe stocks trading above their own 50-day SMA.
"""

import logging
from typing import Dict, Optional, Tuple

import numpy as np
import pandas as pd

from config import MarketRegimeConfig, DEFAULT_CONFIG

logger = logging.getLogger(__name__)


class MarketRegimeFilter:
    """Classifies market regime using IHSG trend + market breadth."""

    def __init__(self, config: MarketRegimeConfig = None):
        self.cfg = config or DEFAULT_CONFIG.regime

    def compute_regime_series(
        self,
        ihsg_df: pd.DataFrame,
        universe_prices: Dict[str, pd.DataFrame],
    ) -> pd.DataFrame:
        """
        Compute regime for every date in ihsg_df.

        Args:
            ihsg_df: IHSG DataFrame with 'close' column, DatetimeIndex
            universe_prices: dict of ticker → DataFrame with 'close', DatetimeIndex

        Returns:
            DataFrame indexed by date with columns:
                ema_fast, ema_medium, ema_slow, breadth, regime, exposure_mult
        """
        if ihsg_df.empty:
            return pd.DataFrame()

        df = ihsg_df[["close"]].copy()

        # Compute IHSG EMAs
        df["ema_fast"] = df["close"].ewm(span=self.cfg.ema_fast, adjust=False).mean()
        df["ema_medium"] = df["close"].ewm(span=self.cfg.ema_medium, adjust=False).mean()
        df["ema_slow"] = df["close"].ewm(span=self.cfg.ema_slow, adjust=False).mean()

        # Compute breadth (% of stocks above their 50-day SMA)
        breadth_series = self._compute_breadth(universe_prices, df.index)
        df["breadth"] = breadth_series

        # Classify regime for each date
        df["regime"] = df.apply(self._classify_row, axis=1)

        # Map exposure multiplier
        df["exposure_mult"] = df["regime"].map(self.cfg.exposure_multiplier)

        # v10: IHSG entry filter uses MA50 instead of MA20.
        # MA20 was too sensitive — blocked entire months (Feb 2025: 0% ok)
        # where mega-winners were breaking out from their troughs.
        # MA50 still prevents entries in true bear markets but allows
        # early recovery entries when mega-winners begin their moves.
        df["ma_50_ihsg"] = df["close"].rolling(50, min_periods=20).mean()
        df["ihsg_above_ma50"] = df["close"] > df["ma_50_ihsg"]
        df["ihsg_daily_return"] = df["close"].pct_change()
        df["ihsg_entry_ok"] = df["ihsg_above_ma50"] & (df["ihsg_daily_return"] > -0.01)

        logger.info(
            f"Regime computed: "
            f"BULL={( df['regime']=='BULL').sum()} days, "
            f"BEAR={(df['regime']=='BEAR').sum()} days, "
            f"SIDEWAYS={(df['regime']=='SIDEWAYS').sum()} days"
        )
        return df

    def get_current_regime(
        self,
        ihsg_df: pd.DataFrame,
        universe_prices: Dict[str, pd.DataFrame],
    ) -> Tuple[str, float]:
        """
        Return the most recent regime and its exposure multiplier.

        Returns:
            (regime_str, exposure_multiplier)
        """
        regime_df = self.compute_regime_series(ihsg_df, universe_prices)
        if regime_df.empty:
            return "SIDEWAYS", self.cfg.exposure_multiplier["SIDEWAYS"]

        last = regime_df.iloc[-1]
        return last["regime"], last["exposure_mult"]

    def _classify_row(self, row: pd.Series) -> str:
        """Classify a single row based on EMA alignment + breadth."""
        ema_f = row["ema_fast"]
        ema_m = row["ema_medium"]
        ema_s = row["ema_slow"]
        breadth = row.get("breadth", 0.5)

        # BULL: EMA20 > EMA50 > EMA200 AND breadth > threshold
        if ema_f > ema_m > ema_s and breadth > self.cfg.breadth_bull_threshold:
            return "BULL"

        # BEAR: EMA20 < EMA50 < EMA200 AND breadth < threshold
        if ema_f < ema_m < ema_s and breadth < self.cfg.breadth_bear_threshold:
            return "BEAR"

        return "SIDEWAYS"

    def _compute_breadth(
        self,
        universe_prices: Dict[str, pd.DataFrame],
        target_dates: pd.DatetimeIndex,
    ) -> pd.Series:
        """
        Compute market breadth: fraction of stocks above their 50-day SMA.

        For each date, count stocks where close > SMA(50), divide by total.
        """
        if not universe_prices:
            # No breadth data — return neutral 0.5
            return pd.Series(0.5, index=target_dates)

        period = self.cfg.breadth_period

        # Build a matrix: dates × stocks, value = 1 if above SMA, else 0
        above_sma = {}
        for ticker, df in universe_prices.items():
            if df.empty or "close" not in df.columns:
                continue
            sma = df["close"].rolling(period, min_periods=period).mean()
            above = (df["close"] > sma).astype(float)
            above_sma[ticker] = above

        if not above_sma:
            return pd.Series(0.5, index=target_dates)

        matrix = pd.DataFrame(above_sma)
        # Breadth = mean across stocks for each date
        breadth = matrix.mean(axis=1)

        # Reindex to target dates (forward-fill for non-trading days)
        breadth = breadth.reindex(target_dates, method="ffill").fillna(0.5)

        return breadth
