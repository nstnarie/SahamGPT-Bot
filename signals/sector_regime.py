"""
Sector Regime Filter (Exp 11)
==============================
Blocks entries when the ticker's sector cohort is in a downtrend.

Rule:
  sector_entry_ok[date] = True iff sector_cohort_index[date] > SMA20(sector_cohort_index)[date]

Cohort index construction:
  - Group tickers by sector (from stock_sectors dict)
  - Equal-weighted price index: each ticker normalized to 1.0 at its first valid close,
    then averaged across all tickers in the sector per date
  - Sectors with <3 tickers → filter bypassed (always ok)
  - Tickers with unknown/empty sector → filter bypassed (always ok)
  - Dates before SMA20 has enough data → treated as ok=True (insufficient history)

Symmetric with signals/market_regime.py Exp 2 IHSG filter. Same rule, per sector.
"""

import logging
from typing import Dict

import pandas as pd

logger = logging.getLogger(__name__)

MIN_TICKERS_PER_SECTOR = 3


class SectorRegimeFilter:
    """Per-sector cohort trend filter. Blocks entries when sector is below its SMA."""

    def __init__(self, ma_period: int = 20, min_tickers: int = MIN_TICKERS_PER_SECTOR):
        self.ma_period = ma_period
        self.min_tickers = min_tickers

    def compute_sector_entry_ok(
        self,
        universe_prices: Dict[str, pd.DataFrame],
        stock_sectors: Dict[str, str],
    ) -> Dict[str, pd.Series]:
        """
        Compute per-sector entry_ok boolean series.

        Returns:
            Dict[sector_name → Series[bool]] indexed by date.
            Sectors with insufficient cohort size are omitted; callers should
            treat missing sectors as always-ok (filter bypassed).
        """
        if not universe_prices or not stock_sectors:
            return {}

        # Group tickers by sector
        sector_to_tickers: Dict[str, list] = {}
        for ticker, sector in stock_sectors.items():
            if not sector:
                continue
            sector_to_tickers.setdefault(sector, []).append(ticker)

        result: Dict[str, pd.Series] = {}

        for sector, tickers in sector_to_tickers.items():
            valid = [t for t in tickers if t in universe_prices and not universe_prices[t].empty]
            if len(valid) < self.min_tickers:
                logger.info(
                    f"Sector '{sector}': {len(valid)} tickers (<{self.min_tickers}) — filter bypassed"
                )
                continue

            # Build wide DataFrame of closes
            closes = {}
            for t in valid:
                df = universe_prices[t]
                if "close" in df.columns:
                    closes[t] = df["close"]
            if len(closes) < self.min_tickers:
                continue

            wide = pd.DataFrame(closes).sort_index()

            # Normalize each ticker to its first valid value (so cohort index starts at 1.0)
            normalized = wide.apply(self._normalize_column, axis=0)

            # Equal-weighted sector index = mean across columns per date (skips NaN)
            sector_index = normalized.mean(axis=1, skipna=True)

            # SMA of the sector index
            sma = sector_index.rolling(self.ma_period, min_periods=self.ma_period).mean()

            # True when above SMA. Also True when SMA is NaN (insufficient history).
            entry_ok = (sector_index > sma) | sma.isna()
            entry_ok = entry_ok.astype(bool)

            result[sector] = entry_ok

            if sma.notna().any():
                pct_ok = entry_ok[sma.notna()].mean() * 100
                logger.info(
                    f"Sector '{sector}': {len(valid)} tickers, "
                    f"{pct_ok:.0f}% of dates entry_ok"
                )

        return result

    @staticmethod
    def _normalize_column(col: pd.Series) -> pd.Series:
        """Normalize a price series to start at 1.0 at its first valid value."""
        first_valid_idx = col.first_valid_index()
        if first_valid_idx is None:
            return col
        first_value = col.loc[first_valid_idx]
        if first_value is None or pd.isna(first_value) or first_value <= 0:
            return col
        return col / first_value
