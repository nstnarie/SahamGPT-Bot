"""
Signal Combiner
================
Combines market regime, big money detection, and technical confirmation
into a final BUY / SELL / HOLD signal for each stock on each date.

Decision tree:
  1. Market regime = BEAR → no new buys (hold or exit)
  2. Big money composite score ≥ threshold → candidate
  3. Technical conditions all pass → BUY signal
  4. Distribution detected (score < exit threshold) → SELL signal
  5. Otherwise → HOLD
"""

import logging
from typing import Dict, List, Optional

import pandas as pd

from config import FrameworkConfig, DEFAULT_CONFIG
from signals.market_regime import MarketRegimeFilter
from signals.big_money import BigMoneyDetector
from signals.technical import TechnicalAnalyzer

logger = logging.getLogger(__name__)


class SignalCombiner:
    """Combines all signal components into final trading signals."""

    def __init__(self, config: FrameworkConfig = DEFAULT_CONFIG):
        self.config = config
        self.regime_filter = MarketRegimeFilter(config.regime)
        self.big_money = BigMoneyDetector(config.big_money)
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
        """
        Generate daily signals for a single stock.

        Returns DataFrame with columns:
            All price columns + indicators + scores + signal
        """
        if price_df.empty:
            return pd.DataFrame()

        # Step 1: Compute market regime for each date
        regime_df = self.regime_filter.compute_regime_series(
            ihsg_df, universe_prices
        )

        # Step 2: Compute technical indicators
        tech_df = self.technical.compute_all_indicators(price_df)

        # Step 3: Compute big money scores
        scores_df = self.big_money.compute_composite_score(
            price_df, foreign_flow_df, broker_df
        )

        # Merge everything
        result = tech_df.copy()
        result = result.join(scores_df, how="left")

        # Align regime data
        if not regime_df.empty:
            result["regime"] = regime_df["regime"].reindex(result.index, method="ffill")
            result["exposure_mult"] = regime_df["exposure_mult"].reindex(
                result.index, method="ffill"
            )
        else:
            result["regime"] = "SIDEWAYS"
            result["exposure_mult"] = self.config.regime.exposure_multiplier["SIDEWAYS"]

        result["regime"] = result["regime"].fillna("SIDEWAYS")
        result["exposure_mult"] = result["exposure_mult"].fillna(0.5)

        # Step 4: Generate signals
        result["signal"] = result.apply(
            lambda row: self._evaluate_signal(row, ticker), axis=1
        )

        # Step 5: Add technical pass flag
        result["technical_pass"] = result.apply(
            lambda row: 1 if self.technical.check_entry_conditions(row) else 0,
            axis=1,
        )

        logger.info(
            f"{ticker}: "
            f"BUY={( result['signal']=='BUY').sum()}, "
            f"SELL={(result['signal']=='SELL').sum()}, "
            f"HOLD={(result['signal']=='HOLD').sum()}"
        )

        return result

    def _evaluate_signal(self, row: pd.Series, ticker: str) -> str:
        """
        Evaluate signal for a single row.

        Logic:
          - If regime is BEAR and exposure_mult is 0 → SELL (exit)
          - If composite_score < exit_threshold → SELL (distribution)
          - If regime allows entry AND composite_score ≥ entry_threshold
            AND technical conditions pass → BUY
          - Otherwise → HOLD
        """
        regime = row.get("regime", "SIDEWAYS")
        exposure = row.get("exposure_mult", 0.5)
        composite = row.get("composite_score", 0.5)

        # SELL conditions (checked first)
        if exposure == 0.0:
            return "SELL"

        if composite < self.config.big_money.score_exit_threshold:
            return "SELL"

        # BUY conditions
        if exposure > 0:
            if composite >= self.config.entry.min_big_money_score:
                if self.technical.check_entry_conditions(row):
                    return "BUY"

        return "HOLD"

    def generate_signals_universe(
        self,
        universe_prices: Dict[str, pd.DataFrame],
        ihsg_df: pd.DataFrame,
        foreign_flows: Optional[Dict[str, pd.DataFrame]] = None,
        broker_data: Optional[Dict[str, pd.DataFrame]] = None,
    ) -> Dict[str, pd.DataFrame]:
        """
        Generate signals for all stocks in the universe.

        Returns dict of ticker → signal DataFrame.
        """
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
