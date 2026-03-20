"""
Foreign flow & broker summary data scraper.

Data sources (all free):
1. IDX website — limited foreign flow data
2. Stockbit / IndoPremier — broker summary (requires web scraping)
3. CSV import — for users who have data from paid providers

Because free real-time broker summary data is difficult to obtain
programmatically from IDX, this module supports:
  (a) Synthetic estimation from Yahoo Finance volume data
  (b) CSV file import for users with access to broker summary data
  (c) Placeholder scraper for IDX API (when available)
"""

import logging
import os
from datetime import date, datetime
from typing import List, Optional

import pandas as pd

from config import FrameworkConfig, DEFAULT_CONFIG
from database.schema import get_session
from database.data_loader import upsert_foreign_flow

logger = logging.getLogger(__name__)


class FlowScraper:
    """
    Handles foreign flow and broker summary data.

    In practice, granular broker summary data requires either:
    - A paid data provider (e.g., RTI Business, Stockbit Pro)
    - Manual CSV export from broker platforms

    This module provides:
    1. A CSV import function for users who have the data
    2. A synthetic estimator that approximates foreign flow
       from price-volume patterns (less accurate but free)
    """

    def __init__(self, config: FrameworkConfig = DEFAULT_CONFIG):
        self.config = config

    # ──────────────────────────────────────────────────────────
    # Method 1: Import from CSV
    # ──────────────────────────────────────────────────────────

    def import_foreign_flow_csv(self, session, filepath: str, ticker: str) -> int:
        """
        Import foreign flow data from CSV file.

        Expected CSV columns:
            date, foreign_buy_value, foreign_sell_value,
            foreign_buy_volume, foreign_sell_volume

        Net values are computed automatically.
        """
        if not os.path.exists(filepath):
            logger.error(f"File not found: {filepath}")
            return 0

        df = pd.read_csv(filepath, parse_dates=["date"])
        df["date"] = df["date"].dt.date

        # Compute net columns if not present
        if "net_foreign_value" not in df.columns:
            df["net_foreign_value"] = (
                df["foreign_buy_value"] - df["foreign_sell_value"]
            )
        if "net_foreign_volume" not in df.columns:
            df["net_foreign_volume"] = (
                df["foreign_buy_volume"] - df["foreign_sell_volume"]
            )

        count = upsert_foreign_flow(session, df, ticker)
        logger.info(f"Imported {count} foreign flow rows for {ticker} from CSV")
        return count

    def import_broker_summary_csv(self, session, filepath: str, ticker: str) -> int:
        """
        Import broker summary data from CSV file.

        Expected CSV columns:
            date, broker_code, buy_value, sell_value,
            buy_volume, sell_volume
        """
        from database.schema import BrokerSummary

        if not os.path.exists(filepath):
            logger.error(f"File not found: {filepath}")
            return 0

        df = pd.read_csv(filepath, parse_dates=["date"])
        df["date"] = df["date"].dt.date

        if "net_value" not in df.columns:
            df["net_value"] = df["buy_value"] - df["sell_value"]
        if "net_volume" not in df.columns:
            df["net_volume"] = df["buy_volume"] - df["sell_volume"]

        count = 0
        for _, row in df.iterrows():
            existing = (
                session.query(BrokerSummary)
                .filter_by(
                    ticker=ticker,
                    date=row["date"],
                    broker_code=row["broker_code"],
                )
                .first()
            )
            if not existing:
                bs = BrokerSummary(
                    ticker=ticker,
                    date=row["date"],
                    broker_code=row["broker_code"],
                    buy_value=float(row.get("buy_value", 0)),
                    sell_value=float(row.get("sell_value", 0)),
                    buy_volume=float(row.get("buy_volume", 0)),
                    sell_volume=float(row.get("sell_volume", 0)),
                    net_value=float(row.get("net_value", 0)),
                    net_volume=float(row.get("net_volume", 0)),
                )
                session.add(bs)
                count += 1
        session.commit()
        logger.info(f"Imported {count} broker summary rows for {ticker}")
        return count

    # ──────────────────────────────────────────────────────────
    # Method 2: Synthetic Foreign Flow Estimation
    # ──────────────────────────────────────────────────────────

    def estimate_foreign_flow_from_prices(
        self, price_df: pd.DataFrame, ticker: str
    ) -> pd.DataFrame:
        """
        Estimate foreign flow from price-volume patterns.

        This is an APPROXIMATION used when real foreign flow data
        is unavailable. The heuristic:
        - On days where price closes in the upper 30% of the day's
          range on high volume → estimate net foreign buy
        - On days where price closes in the lower 30% of the day's
          range on high volume → estimate net foreign sell
        - Volume magnitude scales the estimated flow

        This is NOT a substitute for real data. Use CSV import
        whenever possible.
        """
        if price_df.empty:
            return pd.DataFrame()

        df = price_df.copy()

        # Where in the day's range did the close fall? (0=low, 1=high)
        day_range = df["high"] - df["low"]
        close_position = (df["close"] - df["low"]) / day_range.replace(0, float("nan"))
        close_position = close_position.fillna(0.5)

        # Volume relative to 20-day average
        avg_vol = df["volume"].rolling(20, min_periods=5).mean()
        vol_ratio = df["volume"] / avg_vol.replace(0, float("nan"))
        vol_ratio = vol_ratio.fillna(1.0)

        # Estimate net foreign flow direction & magnitude
        # Positive = accumulation, Negative = distribution
        # Scale: close_position mapped to [-1, 1], then multiply by vol_ratio
        flow_direction = (close_position - 0.5) * 2  # [-1, 1]
        flow_magnitude = flow_direction * vol_ratio

        # Convert to IDR value estimate (rough)
        estimated_value = flow_magnitude * df["value"] * 0.3  # assume ~30% foreign

        result = pd.DataFrame({
            "date": df.index if isinstance(df.index, pd.DatetimeIndex) else df["date"],
            "net_foreign_value": estimated_value.values,
            "net_foreign_volume": (flow_magnitude * df["volume"] * 0.3).values,
            "foreign_buy_value": estimated_value.clip(lower=0).values,
            "foreign_sell_value": (-estimated_value.clip(upper=0)).values,
        })

        if isinstance(df.index, pd.DatetimeIndex):
            result["date"] = df.index.date

        logger.info(
            f"Estimated foreign flow for {ticker}: "
            f"{len(result)} rows (SYNTHETIC — use real data when available)"
        )
        return result

    def estimate_and_store(self, session, price_df: pd.DataFrame, ticker: str):
        """Estimate foreign flow from prices and store in DB."""
        ff_df = self.estimate_foreign_flow_from_prices(price_df, ticker)
        if not ff_df.empty:
            upsert_foreign_flow(session, ff_df, ticker)


class FundamentalScraper:
    """
    Scrapes fundamental data (market cap, P/E, sector) using yfinance.
    """

    def __init__(self, config: FrameworkConfig = DEFAULT_CONFIG):
        self.config = config

    def scrape_stock_info(self, ticker: str) -> dict:
        """Get fundamental data for a single stock via yfinance."""
        import yfinance as yf
        import time

        yf_ticker = f"{ticker}{self.config.scraper.yf_suffix}"
        try:
            stock = yf.Ticker(yf_ticker)
            info = stock.info

            result = {
                "ticker": ticker,
                "name": info.get("longName", info.get("shortName", "")),
                "sector": info.get("sector", ""),
                "industry": info.get("industry", ""),
                "market_cap": info.get("marketCap", 0),
                "shares_outstanding": info.get("sharesOutstanding", 0),
                "free_float_pct": info.get("floatShares", 0) / max(
                    info.get("sharesOutstanding", 1), 1
                ),
            }

            time.sleep(self.config.scraper.request_delay)
            return result

        except Exception as e:
            logger.warning(f"Failed to get info for {ticker}: {e}")
            return {"ticker": ticker}

    def update_stock_master(self, session, tickers: List[str]):
        """Update the stocks master table with fundamental data."""
        from database.schema import Stock

        for ticker in tickers:
            info = self.scrape_stock_info(ticker)
            if not info.get("name"):
                continue

            existing = session.query(Stock).filter_by(ticker=ticker).first()
            if existing:
                for k, v in info.items():
                    if k != "ticker" and v:
                        setattr(existing, k, v)
                existing.last_updated = datetime.utcnow()
            else:
                stock = Stock(
                    ticker=info["ticker"],
                    name=info.get("name", ""),
                    sector=info.get("sector", ""),
                    industry=info.get("industry", ""),
                    market_cap=info.get("market_cap", 0),
                    shares_outstanding=info.get("shares_outstanding", 0),
                    free_float_pct=info.get("free_float_pct", 0),
                )
                session.add(stock)

            session.commit()
            logger.info(f"Updated master data for {ticker}")
