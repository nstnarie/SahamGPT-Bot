"""
Signal Combiner v4 — Breakout + Foreign Flow Confirmation
============================================================
COMPLETELY REBUILT. The old "big money score" approach is gone.

New signal logic:
  1. Market regime ≠ BEAR
  2. PRIMARY: Price breaks above 20-day high with volume spike
  3. CONFIRM: Net foreign flow is positive (real data, not synthetic)
  4. FILTER: RSI not overbought, MACD momentum positive
  5. All conditions true → BUY

Exit logic:
  - Stop-loss: -7% or 1.5×ATR (tighter wins), -8% hard cap
  - Trailing stop at +8% activation
  - Partial profit: sell 30% at +15%
  - Time exit: 15 days with no +3% gain
  - Foreign flow exit: 5 consecutive days of net selling
  - Regime exit: BEAR → close all
"""

import logging
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from config import FrameworkConfig, DEFAULT_CONFIG
from signals.market_regime import MarketRegimeFilter
from signals.technical import TechnicalAnalyzer

logger = logging.getLogger(__name__)


class SignalCombiner:
    """Generates BUY/SELL/HOLD signals using breakout + foreign flow."""

    def __init__(self, config: FrameworkConfig = DEFAULT_CONFIG):
        self.config = config
        self.regime_filter = MarketRegimeFilter(config.regime)
        self.technical = TechnicalAnalyzer(config.technical)

    def generate_signals(
        self,
        ticker: str,
        price_df: pd.DataFrame,
        ihsg_df: pd.DataFrame,
        universe_prices: Dict[str, pd.DataFrame],
        foreign_flow_df: Optional[pd.DataFrame] = None,
        broker_df: Optional[pd.DataFrame] = None,
    ) -> pd.DataFrame:
        """Generate daily signals for a single stock."""
        if price_df.empty:
            return pd.DataFrame()

        # Step 1: Compute market regime
        regime_df = self.regime_filter.compute_regime_series(ihsg_df, universe_prices)

        # Step 2: Compute technical indicators
        tech_df = self.technical.compute_all_indicators(price_df)

        # Step 3: Compute breakout signals
        result = tech_df.copy()
        result = self._add_breakout_signals(result)

        # Step 4: Add foreign flow confirmation
        result = self._add_foreign_flow_signals(result, foreign_flow_df)

        # Align regime
        if not regime_df.empty:
            result["regime"] = regime_df["regime"].reindex(result.index, method="ffill")
            result["exposure_mult"] = regime_df["exposure_mult"].reindex(result.index, method="ffill")
        else:
            result["regime"] = "SIDEWAYS"
            result["exposure_mult"] = 0.5

        result["regime"] = result["regime"].fillna("SIDEWAYS")
        result["exposure_mult"] = result["exposure_mult"].fillna(0.5)

        # Step 5: Combine into final signal
        result["signal"] = result.apply(
            lambda row: self._evaluate_signal(row), axis=1
        )

        # Backward compat columns
        result["composite_score"] = 0.0
        result["foreign_score"] = 0.0
        result["volume_price_score"] = 0.0
        result["broker_score"] = 0.0
        result["technical_pass"] = result["signal"].apply(lambda x: 1 if x == "BUY" else 0)

        buy_count = (result["signal"] == "BUY").sum()
        sell_count = (result["signal"] == "SELL").sum()
        logger.info(f"{ticker}: BUY={buy_count}, SELL={sell_count}, HOLD={len(result) - buy_count - sell_count}")

        return result

    def _add_breakout_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Detect breakout signals.
        Breakout = close > N-day highest high AND volume spike AND close > MA50
        """
        cfg = self.config.breakout

        # 20-day highest high (excluding today — we compare today's close to PRIOR range)
        df["high_20d"] = df["high"].rolling(cfg.breakout_period, min_periods=cfg.breakout_period).max().shift(1)

        # MA50 for trend
        df["ma_50"] = df["close"].rolling(cfg.trend_ma_period, min_periods=30).mean()

        # Volume ratio
        df["vol_avg_20"] = df["volume"].rolling(20, min_periods=5).mean()
        df["vol_ratio"] = df["volume"] / df["vol_avg_20"].replace(0, np.nan)
        df["vol_ratio"] = df["vol_ratio"].fillna(1.0)

        # Breakout conditions
        df["is_breakout"] = (
            (df["close"] > df["high_20d"]) &                    # new 20-day high
            (df["vol_ratio"] >= cfg.volume_spike_min) &          # volume spike
            (df["vol_ratio"] <= cfg.volume_spike_max) &          # not a pump-and-dump
            (df["close"] > df["ma_50"]) &                        # above MA50
            (df["high_20d"].notna())                             # enough data
        )

        return df

    def _add_foreign_flow_signals(
        self, df: pd.DataFrame, ff_df: Optional[pd.DataFrame]
    ) -> pd.DataFrame:
        """
        Add foreign flow confirmation signals.
        
        SMART FILTERING: Automatically detects if a stock is foreign-driven
        or domestic-driven based on the actual foreign flow data.
        
        - Foreign-driven stocks (meaningful FF activity): require FF confirmation
        - Domestic-driven stocks (minimal FF activity): skip FF filter,
          use breakout signal alone
        """
        cfg = self.config.foreign_flow

        if ff_df is None or ff_df.empty:
            # No foreign flow data at all → breakout alone
            df["ff_confirmed"] = True
            df["ff_consecutive_sell"] = 0
            df["is_foreign_driven"] = False
            return df

        # Merge foreign flow with price data
        if "net_foreign_value" in ff_df.columns:
            ff_series = ff_df["net_foreign_value"].reindex(df.index, method="ffill")
        else:
            ff_series = pd.Series(0.0, index=df.index)

        df["net_foreign"] = ff_series.fillna(0)

        # ── AUTO-DETECT: Is this stock foreign-driven? ──
        # Compute the ratio of average |net foreign value| to average traded value
        # If foreigners barely trade it, the ratio will be near zero
        avg_ff_activity = df["net_foreign"].abs().rolling(60, min_periods=20).mean()
        avg_traded_value = (df["close"] * df["volume"]).rolling(60, min_periods=20).mean()
        ff_ratio = avg_ff_activity / avg_traded_value.replace(0, np.nan)
        ff_ratio = ff_ratio.fillna(0)

        # If foreign activity is > 5% of traded value → foreign-driven
        # If < 5% → domestic-driven, skip FF filter
        df["is_foreign_driven"] = ff_ratio > 0.05

        # Is today a net foreign buy day?
        df["ff_positive"] = (df["net_foreign"] > cfg.min_net_foreign_value).astype(int)

        # Rolling count: how many of the past N days were positive?
        df["ff_positive_count"] = df["ff_positive"].rolling(
            cfg.lookback_days, min_periods=1
        ).sum()

        # Confirmation logic:
        # - Foreign-driven stocks: require min_positive_days of lookback_days
        # - Domestic-driven stocks: always confirmed (breakout alone is sufficient)
        ff_meets_threshold = df["ff_positive_count"] >= cfg.min_positive_days
        df["ff_confirmed"] = df["is_foreign_driven"].apply(
            lambda x: True if not x else None  # domestic → always True
        )
        # Fill in foreign-driven rows with actual FF check
        mask_foreign = df["is_foreign_driven"] == True
        df.loc[mask_foreign, "ff_confirmed"] = ff_meets_threshold[mask_foreign]
        df["ff_confirmed"] = df["ff_confirmed"].fillna(True).astype(bool)

        # For exit: count consecutive net foreign sell days
        # Only applies to foreign-driven stocks
        df["ff_is_sell"] = (df["net_foreign"] < -cfg.min_net_foreign_value).astype(int)
        groups = (df["ff_is_sell"] != df["ff_is_sell"].shift()).cumsum()
        df["ff_consecutive_sell"] = df["ff_is_sell"].groupby(groups).cumsum()
        # Domestic-driven stocks: don't trigger FF exit
        df.loc[~df["is_foreign_driven"], "ff_consecutive_sell"] = 0

        return df

    def _evaluate_signal(self, row: pd.Series) -> str:
        """
        Evaluate signal for a single row.

        BUY requires ALL of:
          1. Regime is not BEAR (exposure_mult > 0)
          2. Breakout detected (is_breakout = True)
          3. Foreign flow confirmed (ff_confirmed = True)
          4. RSI in range (40-75)
          5. MACD momentum positive (histogram > 0)

        SELL if:
          - Regime is BEAR
          - Foreign flow heavily negative (5+ consecutive sell days)
        """
        regime = row.get("regime", "SIDEWAYS")
        exposure = row.get("exposure_mult", 0.5)

        # SELL conditions
        if exposure == 0.0:
            return "SELL"

        ff_consec_sell = row.get("ff_consecutive_sell", 0)
        if ff_consec_sell >= self.config.foreign_flow.exit_consecutive_sell_days:
            return "SELL"

        # BUY conditions — ALL must be true
        if exposure > 0:
            is_breakout = row.get("is_breakout", False)
            ff_confirmed = row.get("ff_confirmed", False)
            rsi = row.get("rsi", 50)
            macd_hist = row.get("macd_histogram", 0)

            if (
                is_breakout
                and ff_confirmed
                and self.config.technical.rsi_min <= rsi <= self.config.technical.rsi_max
                and macd_hist > 0
            ):
                return "BUY"

        return "HOLD"

    def generate_signals_universe(
        self,
        universe_prices: Dict[str, pd.DataFrame],
        ihsg_df: pd.DataFrame,
        foreign_flows: Optional[Dict[str, pd.DataFrame]] = None,
        broker_data: Optional[Dict[str, pd.DataFrame]] = None,
    ) -> Dict[str, pd.DataFrame]:
        """Generate signals for all stocks in the universe."""
        foreign_flows = foreign_flows or {}
        broker_data = broker_data or {}
        all_signals = {}

        for ticker, price_df in universe_prices.items():
            try:
                sig_df = self.generate_signals(
                    ticker=ticker,
                    price_df=price_df,
                    ihsg_df=ihsg_df,
                    universe_prices=universe_prices,
                    foreign_flow_df=foreign_flows.get(ticker),
                    broker_df=broker_data.get(ticker),
                )
                all_signals[ticker] = sig_df
            except Exception as e:
                logger.error(f"Error generating signals for {ticker}: {e}")
                continue

        return all_signals
