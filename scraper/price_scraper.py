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
# STOCK UNIVERSE: LQ45 + IDX SMC Liquid (~100 stocks)
# Covers large-caps AND liquid mid-caps (2nd tier)
# Update this list every 6 months when IDX reviews constituents
# (January and July — check idx.co.id for latest)
# ──────────────────────────────────────────────────────────────

LQ45_TICKERS = [
    # ── LQ45 (Large Cap) ──
    "ACES", "ADRO", "AKRA", "AMMN", "AMRT", "ANTM", "ASII", "BBCA",
    "BBNI", "BBRI", "BBTN", "BFIN", "BMRI", "BRPT", "BUKA", "CPIN",
    "CTRA", "ESSA", "EXCL", "GGRM", "GOTO", "HRUM", "ICBP", "INCO",
    "INDF", "INKP", "INTP", "ITMG", "JPFA", "KLBF", "MAPA", "MAPI",
    "MBMA", "MDKA", "MEDC", "MIKA", "PGAS", "PGEO", "SMGR", "TBIG",
    "TINS", "TLKM", "TOWR", "TPIA", "UNTR", "UNVR",

    # ── IDX SMC Liquid (Mid Cap — 2nd Tier) ──
    "AALI", "AGII", "AKPI", "ALTO", "ARNA", "BALI",
    "BBKP", "BBSS", "BCIP", "BIRD", "BJTM", "BSDE",
    "BTPS", "CMRY", "DMAS", "DSNG", "DSSA",
    "ELSA", "EMTK", "ERAA", "FILM", "GJTL", "HEXA", "HMSP",
    "HOKI", "HRTA", "IGAR", "INDY", "INTA", "IPOL", "ISAT",
    "JARR", "JSMR", "KBLI", "KIJA", "LINK",
    "LPPF", "MDIA", "MDLN", "MKPI", "MNCN", "MTEL",
    "MYOR", "NCKL", "NIKL", "PNBN", "PTBA", "PTPP", "PTRO", "PWON", "RALS",
    "SCMA", "SIDO", "SILO", "SMRA", "SRTG", "SSMS",
    "TKIM", "TOTL", "TSPC", "WIKA", "WSBP", "WTON",

    # ── Expansion Batch 1 (Apr 2026 — high-liquidity new additions) ──
    "AADI", "ADMR", "BREN", "BRIS", "CUAN", "DEWA", "PANI", "PSAB",
    "RAJA", "RATU", "WIFI",

    # ── Expansion Batch 2 (Apr 2026 — additional screening universe) ──
    "ADHI", "AGRO", "AMAN", "ARGO", "ARTO", "ASSA", "AVIA", "BNBA",
    "DOID", "ENRG", "IMAS", "KRAS", "POWR", "SMBR", "SMDR", "WIIM",

    # ── Expansion Batch 3 (Apr 2026 — queued additions) ──
    "INET",
]

# Sector mapping for all tickers in the universe.
# Used by Exp 11 (sector cohort momentum filter) as a fallback when the
# stocks table in the database doesn't have sector data (e.g. CI environments
# where the artifact was uploaded by a workflow that doesn't populate stocks).
# Source: yfinance stock.info["sector"] as stored in the local stocks table, Apr 2026.
# Note: yfinance IDX sector labels may not perfectly match IDX/GICS classification.
# Good enough for Exp 11 cohort grouping; refine if the experiment is accepted.
TICKER_SECTORS: dict = {
    "AALI": "Consumer Defensive",
    "ACES": "Consumer Cyclical",
    "ADRO": "Energy",
    "AGII": "Basic Materials",
    "AKPI": "Consumer Cyclical",
    "AKRA": "Energy",
    "ALTO": "Consumer Defensive",
    "AMMN": "Basic Materials",
    "AMRT": "Consumer Defensive",
    "ANTM": "Basic Materials",
    "ARNA": "Industrials",
    "ASII": "Industrials",
    "BALI": "Communication Services",
    "BBCA": "Financial Services",
    "BBKP": "Financial Services",
    "BBNI": "Financial Services",
    "BBRI": "Financial Services",
    "BBSS": "Industrials",
    "BBTN": "Financial Services",
    "BCIP": "Real Estate",
    "BFIN": "Financial Services",
    "BIRD": "Industrials",
    "BJTM": "Financial Services",
    "BMRI": "Financial Services",
    "BRPT": "Basic Materials",
    "BSDE": "Real Estate",
    "BTPS": "Financial Services",
    "BUKA": "Consumer Cyclical",
    "CMRY": "Consumer Defensive",
    "CPIN": "Consumer Defensive",
    "CTRA": "Real Estate",
    "DMAS": "Real Estate",
    "DSNG": "Consumer Defensive",
    "DSSA": "Energy",
    "ELSA": "Energy",
    "EMTK": "Communication Services",
    "ERAA": "Consumer Cyclical",
    "ESSA": "Basic Materials",
    "EXCL": "Communication Services",
    "FILM": "Communication Services",
    "GGRM": "Consumer Defensive",
    "GJTL": "Consumer Cyclical",
    "GOTO": "Technology",
    "HEXA": "Industrials",
    "HMSP": "Consumer Defensive",
    "HOKI": "Consumer Defensive",
    "HRTA": "Consumer Cyclical",
    "HRUM": "Energy",
    "ICBP": "Consumer Defensive",
    "IGAR": "Consumer Cyclical",
    "INCO": "Basic Materials",
    "INDF": "Consumer Defensive",
    "INDY": "Energy",
    "INKP": "Basic Materials",
    "INTA": "Industrials",
    "INTP": "Basic Materials",
    "IPOL": "Consumer Cyclical",
    "ISAT": "Communication Services",
    "ITMG": "Energy",
    "JARR": "Consumer Defensive",
    "JPFA": "Consumer Defensive",
    "JSMR": "Industrials",
    "KBLI": "Industrials",
    "KIJA": "Real Estate",
    "KLBF": "Healthcare",
    "LINK": "Communication Services",
    "LPPF": "Consumer Cyclical",
    "MAPA": "Consumer Cyclical",
    "MAPI": "Consumer Cyclical",
    "MBMA": "Basic Materials",
    "MDIA": "Communication Services",
    "MDKA": "Basic Materials",
    "MDLN": "Real Estate",
    "MEDC": "Energy",
    "MIKA": "Healthcare",
    "MKPI": "Real Estate",
    "MNCN": "Communication Services",
    "MTEL": "Communication Services",
    "MYOR": "Consumer Defensive",
    "NCKL": "Basic Materials",
    "NIKL": "Industrials",
    "PGAS": "Utilities",
    "PGEO": "Utilities",
    "PNBN": "Financial Services",
    "PTBA": "Energy",
    "PTPP": "Industrials",
    "PTRO": "Basic Materials",
    "PWON": "Real Estate",
    "RALS": "Consumer Cyclical",
    "SCMA": "Communication Services",
    "SIDO": "Healthcare",
    "SILO": "Healthcare",
    "SMGR": "Basic Materials",
    "SMRA": "Real Estate",
    "SRTG": "Financial Services",
    "SSMS": "Consumer Defensive",
    "TBIG": "Communication Services",
    "TINS": "Basic Materials",
    "TKIM": "Basic Materials",
    "TLKM": "Communication Services",
    "TOTL": "Industrials",
    "TOWR": "Real Estate",
    "TPIA": "Basic Materials",
    "TSPC": "Industrials",
    "UNTR": "Basic Materials",
    "UNVR": "Consumer Defensive",
    "WIKA": "Industrials",
    "WSBP": "Basic Materials",
    "WTON": "Basic Materials",
}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    scraper = PriceScraper()
    df = scraper.scrape_stock("BBCA", start_date="2024-01-01")
    print(df.head())
