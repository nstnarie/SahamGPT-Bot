"""
Signal Combiner v5 — Historical Resistance Breakout + Foreign Flow
====================================================================
Entry: stock breaks 60-day high (historical resistance) with volume spike
       + foreign flow confirmation for foreign-driven stocks
       + minimum price filter (>= Rp 150)
Exit:  trend-following for high performers (MA10 break)
       + 5-day minimum hold before stop fires
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

    def __init__(self, config: FrameworkConfig = DEFAULT_CONFIG):
        self.config = config
        self.regime_filter = MarketRegimeFilter(config.regime)
        self.technical = TechnicalAnalyzer(config.technical)

    def generate_signals(self, ticker, price_df, ihsg_df, universe_prices,
                         foreign_flow_df=None, broker_df=None):
        if price_df.empty:
            return pd.DataFrame()

        regime_df = self.regime_filter.compute_regime_series(ihsg_df, universe_prices)
        tech_df = self.technical.compute_all_indicators(price_df)
        result = tech_df.copy()

        # Add breakout detection (60-day high = historical resistance)
        result = self._add_breakout_signals(result)

        # Add foreign flow confirmation
        result = self._add_foreign_flow_signals(result, foreign_flow_df)

        # Add broker accumulation/distribution score
        result = self._add_accumulation_signals(result, broker_df)

        # Add trend exit indicators (MA10 for high-performers)
        result["ma_10"] = result["close"].rolling(10, min_periods=5).mean()

        # Align regime
        if not regime_df.empty:
            result["regime"] = regime_df["regime"].reindex(result.index, method="ffill")
            result["exposure_mult"] = regime_df["exposure_mult"].reindex(result.index, method="ffill")
        else:
            result["regime"] = "SIDEWAYS"
            result["exposure_mult"] = 0.5

        result["regime"] = result["regime"].fillna("SIDEWAYS")
        result["exposure_mult"] = result["exposure_mult"].fillna(0.5)

        # Generate signals
        result["signal"] = result.apply(lambda row: self._evaluate_signal(row), axis=1)

        # Compat columns
        result["composite_score"] = 0.0
        result["foreign_score"] = 0.0
        result["volume_price_score"] = 0.0
        result["broker_score"] = 0.0
        result["technical_pass"] = result["signal"].apply(lambda x: 1 if x == "BUY" else 0)

        buy_count = (result["signal"] == "BUY").sum()
        sell_count = (result["signal"] == "SELL").sum()
        logger.info(f"{ticker}: BUY={buy_count}, SELL={sell_count}, HOLD={len(result)-buy_count-sell_count}")

        return result

    def _add_breakout_signals(self, df):
        """
        Breakout = close exceeds N-day highest high (historical resistance).
        
        v6 additions:
        - Selling pressure filter: reject candles with long upper shadow
          (MYOR Apr 25 2025 — price went up but heavy selling pushed it down)
        - Foreign flow trend is checked separately in _add_foreign_flow_signals
        """
        cfg = self.config.breakout

        # 60-day highest high (shift 1 = compare to PRIOR range)
        df["high_Nd"] = df["high"].rolling(
            cfg.breakout_period, min_periods=cfg.breakout_period
        ).max().shift(1)

        # MA50 for trend confirmation
        df["ma_50"] = df["close"].rolling(cfg.trend_ma_period, min_periods=30).mean()

        # Volume ratio
        if "vol_avg_20" not in df.columns:
            df["vol_avg_20"] = df["volume"].rolling(20, min_periods=5).mean()
        if "vol_ratio" not in df.columns:
            df["vol_ratio"] = df["volume"] / df["vol_avg_20"].replace(0, np.nan)
            df["vol_ratio"] = df["vol_ratio"].fillna(1.0)

        # Minimum price filter
        min_price = self.config.universe.min_stock_price

        # Breakout conditions
        # v10: removed close > ma_50 — Step 2 analysis: 68% of mega-winners have
        # bearish MA alignment at trough; requiring MA50 blocks 54% of them.
        # v10: removed selling pressure filter — blocked CUAN (+511%) and SMDR
        # (+117%) on their breakout day. Stop loss handles bad candle entries
        # at lower cost than missing mega-winners.
        df["has_selling_pressure"] = False  # kept for signal output compatibility
        df["is_breakout"] = (
            (df["close"] > df["high_Nd"]) &              # breaks resistance
            (df["vol_ratio"] >= cfg.volume_spike_min) &   # volume spike
            (df["vol_ratio"] <= cfg.volume_spike_max) &   # not pump-and-dump
            (df["close"] >= min_price) &                  # minimum price filter
            (df["high_Nd"].notna())                       # enough data
        )

        return df

    def _add_foreign_flow_signals(self, df, ff_df):
        """
        Smart foreign flow with TREND detection.
        
        v6: For foreign-driven stocks, we now check TWO things:
          1. Recent activity: 3 of 5 days net foreign buy (existing)
          2. NEW — Flow TREND: the 5-day cumulative foreign flow must be 
             INCREASING (trending up), not just occasionally positive.
        
        This catches the ADRO May 19 2025 case: stock went up with volume
        but foreign flow was actually net SELL. The old logic might pass
        if 3 of the prior 5 days were positive, but the TREND was turning
        negative. Now we check both.
        """
        cfg = self.config.foreign_flow

        if ff_df is None or ff_df.empty:
            df["ff_confirmed"] = True
            df["ff_consecutive_sell"] = 0
            df["is_foreign_driven"] = False
            df["ff_trend_positive"] = True
            return df

        if "net_foreign_value" in ff_df.columns:
            ff_series = ff_df["net_foreign_value"].reindex(df.index, method="ffill")
        else:
            ff_series = pd.Series(0.0, index=df.index)

        df["net_foreign"] = ff_series.fillna(0)

        # Auto-detect foreign-driven stocks using directional consistency
        # consistency = abs(sum(net)) / sum(abs(net)) over 60 days
        # High consistency = foreigners persistently on one side (informative signal)
        # Low consistency = random buy/sell (noise — FF filter would hurt)
        rolling_sum = df["net_foreign"].rolling(60, min_periods=20).sum()
        rolling_abs_sum = df["net_foreign"].abs().rolling(60, min_periods=20).sum()
        consistency = rolling_sum.abs() / rolling_abs_sum.replace(0, np.nan)
        df["is_foreign_driven"] = consistency.fillna(0) > 0.20

        # ── Check 1: Recent positive days (existing logic) ──
        df["ff_positive"] = (df["net_foreign"] > cfg.min_net_foreign_value).astype(int)
        df["ff_positive_count"] = df["ff_positive"].rolling(
            cfg.lookback_days, min_periods=1
        ).sum()
        ff_meets_count = df["ff_positive_count"] >= cfg.min_positive_days

        # ── Check 2 (NEW): Foreign flow TREND ──
        # The 5-day rolling sum of net foreign value must be positive
        # AND today's net foreign must not be negative
        # This catches ADRO: even if 3 of 5 prior days were positive,
        # if the breakout day itself has net foreign SELL, the trend is turning
        df["ff_rolling_sum"] = df["net_foreign"].rolling(
            cfg.lookback_days, min_periods=1
        ).sum()
        df["ff_trend_positive"] = (
            (df["ff_rolling_sum"] > 0) &       # cumulative trend is positive
            (df["net_foreign"] >= 0)            # today is not a net sell day
        )

        # ── Combined confirmation for foreign-driven stocks ──
        # Must pass BOTH: recent positive days AND trend is positive
        ff_full_confirm = ff_meets_count & df["ff_trend_positive"]

        df["ff_confirmed"] = True  # default for domestic stocks
        mask_foreign = df["is_foreign_driven"] == True
        df.loc[mask_foreign, "ff_confirmed"] = ff_full_confirm[mask_foreign]
        df["ff_confirmed"] = df["ff_confirmed"].fillna(True).astype(bool)

        # Consecutive sell days for exit
        df["ff_is_sell"] = (df["net_foreign"] < -cfg.min_net_foreign_value).astype(int)
        groups = (df["ff_is_sell"] != df["ff_is_sell"].shift()).cumsum()
        df["ff_consecutive_sell"] = df["ff_is_sell"].groupby(groups).cumsum()
        df.loc[~df["is_foreign_driven"], "ff_consecutive_sell"] = 0

        return df

    def _add_accumulation_signals(self, df, broker_df):
        """
        Broker accumulation signals for entry and exit.

        Two metrics:
        1. accumulation_score (count-based) — used for hold extension (v8)
        2. top_broker_acc (value-weighted, top-5 Asing by activity) — for entry filter

        For entry: uses top_broker_acc because it captures big money direction.
        Count-based scores are noise (many small brokers ≠ market direction).
        """
        if broker_df is None or broker_df.empty or "accumulation_score" not in broker_df.columns:
            df["accumulation_score"] = 0
            df["top_broker_acc"] = 0
            return df

        score = broker_df["accumulation_score"].reindex(df.index, method="ffill").fillna(0)
        df["accumulation_score"] = score

        if "top_broker_acc" in broker_df.columns:
            top_acc = broker_df["top_broker_acc"].reindex(df.index, method="ffill").fillna(0)
            df["top_broker_acc"] = top_acc
        else:
            df["top_broker_acc"] = 0

        return df

    def _evaluate_signal(self, row):
        """
        BUY: breakout + FF confirmed + regime not BEAR
        SELL: regime BEAR or FF heavily negative

        v10: removed RSI 40-75 and MACD > 0 checks.
        Step 2 analysis: 84% of mega-winners have RSI < 40 at trough (median 26),
        76% have negative MACD. These filters blocked 80% of mega-winners.
        """
        exposure = row.get("exposure_mult", 0.5)

        if exposure == 0.0:
            return "SELL"

        ff_consec_sell = row.get("ff_consecutive_sell", 0)
        if ff_consec_sell >= self.config.foreign_flow.exit_consecutive_sell_days:
            return "SELL"

        if exposure > 0:
            is_breakout = row.get("is_breakout", False)
            ff_confirmed = row.get("ff_confirmed", False)

            if is_breakout and ff_confirmed:
                return "BUY"

        return "HOLD"

    def generate_signals_universe(self, universe_prices, ihsg_df,
                                   foreign_flows=None, broker_data=None):
        foreign_flows = foreign_flows or {}
        broker_data = broker_data or {}
        all_signals = {}

        for ticker, price_df in universe_prices.items():
            try:
                sig_df = self.generate_signals(
                    ticker, price_df, ihsg_df, universe_prices,
                    foreign_flows.get(ticker), broker_data.get(ticker),
                )
                all_signals[ticker] = sig_df
            except Exception as e:
                logger.error(f"Error for {ticker}: {e}")
        return all_signals
