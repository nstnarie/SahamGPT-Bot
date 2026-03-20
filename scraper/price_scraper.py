"""
Historical OHLCV scraper for IDX stocks.
Primary source: Yahoo Finance via yfinance (free, no API key required).
IDX tickers use the .JK suffix on Yahoo Finance.
"""

import logging
import time
from datetime import datetime, timedelta
from typing import List, Optional

import pandas as pd

try:
    import yfinance as yf
except ImportError:
    raise ImportError("Install yfinance: pip install yfinance")

from config import FrameworkConfig, DEFAULT_CONFIG
from database.schema import get_session, DailyPrice
from database.data_loader import upsert_daily_prices, upsert_index_daily

logger = logging.getLogger(__name__)


class PriceScraper:
    """
    Scrapes daily OHLCV data from Yahoo Finance for IDX stocks.
    Yahoo Finance uses .JK suffix for IDX (e.g., BBCA.JK).
    """

    def __init__(self, config: FrameworkConfig = DEFAULT_CONFIG):
        self.config = config
        self.delay = config.scraper.request_delay
        self.max_retries = config.scraper.max_retries
        self.backoff = config.scraper.retry_backoff

    def scrape_stock(self, ticker: str,
                     start_date: str = "2021-01-01",
                     end_date: Optional[str] = None) -> pd.DataFrame:
        """
        Download daily OHLCV for a single IDX stock.

        Args:
            ticker: IDX ticker without suffix (e.g., "BBCA")
            start_date: Start date string "YYYY-MM-DD"
            end_date: End date string (defaults to today)

        Returns:
            DataFrame with columns: date, open, high, low, close, volume, value, adj_close
        """
        yf_ticker = f"{ticker}{self.config.scraper.yf_suffix}"
        if end_date is None:
            end_date = datetime.now().strftime("%Y-%m-%d")

        logger.info(f"Downloading {yf_ticker} from {start_date} to {end_date}")

        for attempt in range(1, self.max_retries + 1):
            try:
                stock = yf.Ticker(yf_ticker)
                df = stock.history(start=start_date, end=end_date, auto_adjust=False)

                if df.empty:
                    logger.warning(f"No data returned for {yf_ticker}")
                    return pd.DataFrame()

                # Standardise column names
                df = df.reset_index()
                df.columns = [c.lower().replace(" ", "_") for c in df.columns]

                # Rename to our schema
                rename_map = {
                    "adj_close": "adj_close",
                    "adj close": "adj_close",
                }
                df.rename(columns=rename_map, inplace=True)

                # Ensure date column is date type
                if "date" in df.columns:
                    df["date"] = pd.to_datetime(df["date"]).dt.date
                elif "datetime" in df.columns:
                    df["date"] = pd.to_datetime(df["datetime"]).dt.date

                # Compute traded value (approx) if not available
                if "value" not in df.columns:
                    df["value"] = df["close"] * df["volume"]

                # Ensure adj_close exists
                if "adj_close" not in df.columns:
                    df["adj_close"] = df["close"]

                # Select final columns
                cols = ["date", "open", "high", "low", "close", "volume", "value", "adj_close"]
                for c in cols:
                    if c not in df.columns:
                        df[c] = None
                df = df[cols]

                # Drop rows with all-NaN prices
                df = df.dropna(subset=["close"])

                logger.info(f"Got {len(df)} rows for {ticker}")
                time.sleep(self.delay)
                return df

            except Exception as e:
                wait = self.delay * (self.backoff ** (attempt - 1))
                logger.warning(
                    f"Attempt {attempt}/{self.max_retries} failed for {yf_ticker}: {e}. "
                    f"Retrying in {wait:.1f}s"
                )
                time.sleep(wait)

        logger.error(f"All retries exhausted for {yf_ticker}")
        return pd.DataFrame()

    def scrape_index(self, index_symbol: str = "^JKSE",
                     start_date: str = "2021-01-01",
                     end_date: Optional[str] = None) -> pd.DataFrame:
        """Download IHSG (Jakarta Composite Index) data."""
        if end_date is None:
            end_date = datetime.now().strftime("%Y-%m-%d")

        logger.info(f"Downloading index {index_symbol}")

        for attempt in range(1, self.max_retries + 1):
            try:
                idx = yf.Ticker(index_symbol)
                df = idx.history(start=start_date, end=end_date, auto_adjust=False)

                if df.empty:
                    logger.warning(f"No data for index {index_symbol}")
                    return pd.DataFrame()

                df = df.reset_index()
                df.columns = [c.lower().replace(" ", "_") for c in df.columns]

                if "date" in df.columns:
                    df["date"] = pd.to_datetime(df["date"]).dt.date
                elif "datetime" in df.columns:
                    df["date"] = pd.to_datetime(df["datetime"]).dt.date

                cols = ["date", "open", "high", "low", "close", "volume"]
                for c in cols:
                    if c not in df.columns:
                        df[c] = None
                df = df[cols].dropna(subset=["close"])

                logger.info(f"Got {len(df)} index rows")
                time.sleep(self.delay)
                return df

            except Exception as e:
                wait = self.delay * (self.backoff ** (attempt - 1))
                logger.warning(f"Index scrape attempt {attempt} failed: {e}")
                time.sleep(wait)

        logger.error(f"All retries exhausted for index {index_symbol}")
        return pd.DataFrame()

    def scrape_and_store(self, session, tickers: List[str],
                          start_date: str = "2021-01-01"):
        """Scrape multiple stocks and store in database."""
        # First, scrape and store the index
        idx_df = self.scrape_index(start_date=start_date)
        if not idx_df.empty:
            upsert_index_daily(session, idx_df, "IHSG")

        # Then each stock
        for ticker in tickers:
            df = self.scrape_stock(ticker, start_date=start_date)
            if not df.empty:
                upsert_daily_prices(session, df, ticker)
            else:
                logger.warning(f"Skipping {ticker} — no data")


# ──────────────────────────────────────────────────────────────
# LQ45 CONSTITUENT LIST (as of latest review — update periodically)
# ──────────────────────────────────────────────────────────────

LQ45_TICKERS = [
    "ACES", "ADRO", "AKRA", "AMMN", "AMRT", "ANTM", "ASII", "BBCA",
    "BBNI", "BBRI", "BBTN", "BFIN", "BMRI", "BRPT", "BUKA", "CPIN",
    "ESSA", "EXCL", "GGRM", "GOTO", "HRUM", "ICBP", "INCO", "INDF",
    "INKP", "INTP", "ITMG", "JPFA", "KLBF", "MAPI", "MBMA", "MDKA",
    "MEDC", "MIKA", "PGAS", "PGEO", "SMGR", "TBIG", "TINS", "TLKM",
    "TOWR", "TPIA", "UNTR", "UNVR", "WIKA",
]


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    scraper = PriceScraper()
    df = scraper.scrape_stock("BBCA", start_date="2024-01-01")
    print(df.head())
