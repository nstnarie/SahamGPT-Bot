"""
Big Money / Institutional Flow Detection
==========================================
Three complementary methods to detect institutional accumulation or distribution.

Method 1 — Foreign Flow Analysis
    Consecutive days of significant net foreign buying relative to avg volume.

Method 2 — Volume-Price Analysis
    Accumulation signatures: high volume on up-days, low volume on down-days.
    Uses OBV slope and Accumulation/Distribution line.

Method 3 — Broker Summary Analysis
    Known institutional broker codes showing net accumulation.

Each method produces a score from 0.0 (distribution) to 1.0 (strong accumulation).
Weighted composite score determines the final "big money" signal.
"""

import logging
from typing import Dict, Optional

import numpy as np
import pandas as pd

from config import BigMoneyConfig, DEFAULT_CONFIG

logger = logging.getLogger(__name__)


class BigMoneyDetector:
    """Detects institutional accumulation / distribution in IDX stocks."""

    def __init__(self, config: BigMoneyConfig = None):
        self.cfg = config or DEFAULT_CONFIG.big_money

    def compute_composite_score(
        self,
        price_df: pd.DataFrame,
        foreign_flow_df: Optional[pd.DataFrame] = None,
        broker_df: Optional[pd.DataFrame] = None,
    ) -> pd.DataFrame:
        """
        Compute the composite big-money score for every date.

        Args:
            price_df: OHLCV DataFrame with DatetimeIndex
            foreign_flow_df: foreign flow DataFrame (optional)
            broker_df: broker summary DataFrame (optional)

        Returns:
            DataFrame with columns:
                foreign_score, volume_price_score, broker_score, composite_score
        """
        scores = pd.DataFrame(index=price_df.index)

        # Method 1: Foreign flow
        scores["foreign_score"] = self._foreign_flow_score(
            price_df, foreign_flow_df
        )

        # Method 2: Volume-price analysis
        scores["volume_price_score"] = self._volume_price_score(price_df)

        # Method 3: Broker summary
        scores["broker_score"] = self._broker_summary_score(
            price_df, broker_df
        )

        # Weighted composite
        w = self.cfg
        scores["composite_score"] = (
            w.weight_foreign_flow * scores["foreign_score"]
            + w.weight_volume_price * scores["volume_price_score"]
            + w.weight_broker_summary * scores["broker_score"]
        )

        # Clip to [0, 1]
        scores["composite_score"] = scores["composite_score"].clip(0.0, 1.0)

        return scores

    # ──────────────────────────────────────────────────────────
    # Method 1: Foreign Flow Score
    # ──────────────────────────────────────────────────────────

    def _foreign_flow_score(
        self,
        price_df: pd.DataFrame,
        ff_df: Optional[pd.DataFrame],
    ) -> pd.Series:
        """
        Score based on consecutive days of net foreign buying.

        Logic:
          1. Compute 20-day average volume
          2. Check if daily net foreign buy > threshold × avg_volume
          3. Count consecutive positive days
          4. Score = min(consecutive_days / required_days, 1.0)
             Negative if consecutive net selling
        """
        if ff_df is None or ff_df.empty:
            # No foreign flow data — return neutral
            return pd.Series(0.5, index=price_df.index)

        # Align indices
        df = price_df[["volume"]].copy()
        df["avg_vol_20"] = df["volume"].rolling(20, min_periods=5).mean()

        # Merge foreign flow
        if "net_foreign_volume" in ff_df.columns:
            df = df.join(ff_df[["net_foreign_volume"]], how="left")
        else:
            df["net_foreign_volume"] = 0

        df["net_foreign_volume"] = df["net_foreign_volume"].fillna(0)

        # Is today a significant foreign buy day?
        threshold = self.cfg.foreign_vol_threshold
        df["is_significant_buy"] = (
            df["net_foreign_volume"] > threshold * df["avg_vol_20"]
        ).astype(int)
        df["is_significant_sell"] = (
            df["net_foreign_volume"] < -threshold * df["avg_vol_20"]
        ).astype(int)

        # Count consecutive significant buy/sell days
        df["consec_buy"] = self._consecutive_count(df["is_significant_buy"])
        df["consec_sell"] = self._consecutive_count(df["is_significant_sell"])

        required = self.cfg.foreign_consec_days

        # Score: accumulation → 0.5–1.0, distribution → 0.0–0.5
        buy_score = (df["consec_buy"] / required).clip(0, 1) * 0.5 + 0.5
        sell_score = 0.5 - (df["consec_sell"] / required).clip(0, 1) * 0.5

        # Use buy_score when buying, sell_score when selling, 0.5 otherwise
        score = pd.Series(0.5, index=df.index)
        score[df["consec_buy"] > 0] = buy_score[df["consec_buy"] > 0]
        score[df["consec_sell"] > 0] = sell_score[df["consec_sell"] > 0]

        return score

    # ──────────────────────────────────────────────────────────
    # Method 2: Volume-Price Score
    # ──────────────────────────────────────────────────────────

    def _volume_price_score(self, price_df: pd.DataFrame) -> pd.Series:
        """
        Score based on volume-price accumulation signatures.

        Components:
          A. Volume spike on up-days (bullish) vs. down-days (bearish)
          B. OBV (On-Balance Volume) 10-day slope direction
          C. Accumulation/Distribution line trend

        Each sub-score is 0–1; averaged to produce final score.
        """
        df = price_df.copy()

        # ── A. Volume spike analysis ──
        avg_vol = df["volume"].rolling(20, min_periods=5).mean()
        vol_ratio = df["volume"] / avg_vol.replace(0, np.nan)
        vol_ratio = vol_ratio.fillna(1.0)

        price_change = df["close"].pct_change()
        spike_threshold = self.cfg.volume_spike_multiplier

        # Up-day spike: price up + volume > 2× average
        up_spike = ((price_change > 0) & (vol_ratio > spike_threshold)).astype(float)
        # Down-day spike: price down + volume > 2× average (bearish)
        down_spike = ((price_change < 0) & (vol_ratio > spike_threshold)).astype(float)

        # Rolling sum over 10 days
        up_spikes_10d = up_spike.rolling(10, min_periods=1).sum()
        down_spikes_10d = down_spike.rolling(10, min_periods=1).sum()
        total_spikes = up_spikes_10d + down_spikes_10d
        spike_ratio = up_spikes_10d / total_spikes.replace(0, np.nan)
        spike_score = spike_ratio.fillna(0.5)  # neutral if no spikes

        # ── B. OBV slope ──
        obv = self._compute_obv(df)
        obv_slope = obv.rolling(self.cfg.obv_slope_lookback, min_periods=3).apply(
            lambda x: np.polyfit(range(len(x)), x, 1)[0] if len(x) > 1 else 0,
            raw=False,
        )
        # Normalise slope to 0–1 using sigmoid-like transform
        obv_score = 1 / (1 + np.exp(-obv_slope / (obv.rolling(20).std().replace(0, 1))))
        obv_score = obv_score.fillna(0.5)

        # ── C. Accumulation/Distribution line ──
        ad_line = self._compute_ad_line(df)
        ad_slope = ad_line.rolling(self.cfg.ad_line_lookback, min_periods=3).apply(
            lambda x: np.polyfit(range(len(x)), x, 1)[0] if len(x) > 1 else 0,
            raw=False,
        )
        ad_score = 1 / (1 + np.exp(-ad_slope / (ad_line.rolling(20).std().replace(0, 1))))
        ad_score = ad_score.fillna(0.5)

        # Average the three sub-scores
        combined = (spike_score + obv_score + ad_score) / 3.0
        return combined.clip(0, 1)

    # ──────────────────────────────────────────────────────────
    # Method 3: Broker Summary Score
    # ──────────────────────────────────────────────────────────

    def _broker_summary_score(
        self,
        price_df: pd.DataFrame,
        broker_df: Optional[pd.DataFrame],
    ) -> pd.Series:
        """
        Score based on institutional broker net activity.

        If broker data is available:
          1. Sum net_value for institutional broker codes per day
          2. Compare to daily traded value
          3. Score based on consecutive days of institutional accumulation

        If no broker data → fall back to volume-weighted close position
        (a rough proxy: if close is near the high on heavy volume,
         it suggests large buyers were active).
        """
        if broker_df is not None and not broker_df.empty:
            return self._broker_score_from_data(price_df, broker_df)
        else:
            return self._broker_score_proxy(price_df)

    def _broker_score_from_data(
        self, price_df: pd.DataFrame, broker_df: pd.DataFrame
    ) -> pd.Series:
        """Score using actual broker summary data."""
        inst_brokers = set(self.cfg.institutional_brokers)

        # Filter to institutional brokers
        inst_df = broker_df[broker_df["broker_code"].isin(inst_brokers)]

        # Sum net value per date
        daily_inst = inst_df.groupby(inst_df.index)["net_value"].sum()

        # Merge with price data
        df = price_df[["value"]].copy()
        df["inst_net"] = daily_inst
        df["inst_net"] = df["inst_net"].fillna(0)

        # Is institutional buying significant?
        threshold = self.cfg.broker_net_buy_threshold
        df["is_inst_buy"] = (df["inst_net"] > threshold * df["value"]).astype(int)
        df["is_inst_sell"] = (df["inst_net"] < -threshold * df["value"]).astype(int)

        df["consec_buy"] = self._consecutive_count(df["is_inst_buy"])
        df["consec_sell"] = self._consecutive_count(df["is_inst_sell"])

        required = self.cfg.broker_consec_days
        buy_score = (df["consec_buy"] / required).clip(0, 1) * 0.5 + 0.5
        sell_score = 0.5 - (df["consec_sell"] / required).clip(0, 1) * 0.5

        score = pd.Series(0.5, index=df.index)
        score[df["consec_buy"] > 0] = buy_score[df["consec_buy"] > 0]
        score[df["consec_sell"] > 0] = sell_score[df["consec_sell"] > 0]
        return score

    def _broker_score_proxy(self, price_df: pd.DataFrame) -> pd.Series:
        """
        Proxy when no broker data is available.
        Uses VWAP deviation: if close is above VWAP, suggests net buying pressure.
        """
        df = price_df.copy()

        # Approximate VWAP as (H + L + C) / 3 weighted by volume
        typical_price = (df["high"] + df["low"] + df["close"]) / 3
        vwap_approx = (
            (typical_price * df["volume"]).rolling(20, min_periods=5).sum()
            / df["volume"].rolling(20, min_periods=5).sum()
        )

        # Deviation: positive = close above VWAP (buying), negative = below
        deviation = (df["close"] - vwap_approx) / vwap_approx.replace(0, np.nan)
        deviation = deviation.fillna(0)

        # Map to 0–1 score using sigmoid
        score = 1 / (1 + np.exp(-deviation * 20))  # scale factor for sensitivity
        return score.clip(0, 1)

    # ──────────────────────────────────────────────────────────
    # Helper Functions
    # ──────────────────────────────────────────────────────────

    @staticmethod
    def _compute_obv(df: pd.DataFrame) -> pd.Series:
        """Compute On-Balance Volume."""
        price_change = df["close"].diff()
        direction = pd.Series(0, index=df.index, dtype=float)
        direction[price_change > 0] = 1
        direction[price_change < 0] = -1
        obv = (direction * df["volume"]).cumsum()
        return obv

    @staticmethod
    def _compute_ad_line(df: pd.DataFrame) -> pd.Series:
        """Compute Accumulation/Distribution line."""
        high_low = df["high"] - df["low"]
        # Money Flow Multiplier = ((Close - Low) - (High - Close)) / (High - Low)
        mfm = ((df["close"] - df["low"]) - (df["high"] - df["close"])) / high_low.replace(0, np.nan)
        mfm = mfm.fillna(0)
        # Money Flow Volume
        mfv = mfm * df["volume"]
        # Cumulative A/D line
        return mfv.cumsum()

    @staticmethod
    def _consecutive_count(series: pd.Series) -> pd.Series:
        """
        Count consecutive 1s in a binary series.
        Resets to 0 whenever a 0 appears.
        """
        # Group by changes: new group whenever value changes
        groups = (series != series.shift()).cumsum()
        counts = series.groupby(groups).cumsum()
        return counts
