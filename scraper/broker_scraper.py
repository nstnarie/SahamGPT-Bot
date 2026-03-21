"""
Stockbit Broker Summary Scraper
=================================
Scrapes daily broker summary data from Stockbit's internal API.

Stockbit API endpoints (requires authentication):
  - Login: POST https://exodus.stockbit.com/login
  - Broker Summary: GET https://exodus.stockbit.com/trading-activity/broker-summary/{ticker}

The scraper:
  1. Logs in with your Stockbit credentials
  2. For each stock, fetches the broker summary (top buyers/sellers)
  3. Classifies brokers as foreign/domestic/institutional
  4. Stores in the BrokerSummary table
  5. Also computes aggregated foreign flow from actual broker data

Required GitHub Secrets:
  - STOCKBIT_USERNAME (your Stockbit email)
  - STOCKBIT_PASSWORD (your Stockbit password)

Rate limit: ~40 requests per 5 minutes. The scraper includes
delays to stay well under this limit.
"""

import logging
import os
import time
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional, Tuple

import requests

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────
# KNOWN BROKER CLASSIFICATIONS
# ──────────────────────────────────────────────────────────────
# Source: IDX broker codes, publicly available
# Foreign brokers are key — their net buy/sell is the real "smart money" signal

FOREIGN_BROKERS = {
    "CS",  # Credit Suisse → UBS (now)
    "UB",  # UBS Securities
    "AK",  # UBS Sekuritas
    "DX",  # Macquarie Sekuritas
    "CG",  # Citigroup
    "GS",  # Goldman Sachs (rarely active on IDX)
    "ML",  # Merrill Lynch
    "MS",  # Morgan Stanley
    "JP",  # JP Morgan
    "RX",  # Nomura
    "DB",  # Deutsche Bank
    "BK",  # BNP Paribas
    "CC",  # Mandiri Sekuritas (large foreign client flow)
    "YP",  # Mirae Asset (significant foreign flow)
    "KZ",  # Danareksa (institutional)
    "CL",  # CLSA
    "GR",  # Trimegah (significant institutional)
}

INSTITUTIONAL_BROKERS = {
    "PD",  # CGS-CIMB
    "IF",  # Samsung Sekuritas
    "NI",  # BNI Sekuritas
    "BW",  # BWS Sekuritas
    "OD",  # SBI Sekuritas
    "AI",  # Ajaib Sekuritas
    "ZP",  # Stockbit Sekuritas
    "TP",  # Trimegah Sekuritas
    "KK",  # Philip Sekuritas
    "AG",  # Artha Graha
    "BZ",  # BCA Sekuritas
    "EP",  # MNC Sekuritas
}


class StockbitBrokerScraper:
    """
    Scrapes broker summary data from Stockbit.
    """

    BASE_URL = "https://exodus.stockbit.com"
    LOGIN_URL = f"{BASE_URL}/login"
    BROKER_SUMMARY_URL = f"{BASE_URL}/trading-activity/broker-summary"

    def __init__(self, username: str = None, password: str = None):
        self.username = username or os.getenv("STOCKBIT_USERNAME", "")
        self.password = password or os.getenv("STOCKBIT_PASSWORD", "")
        self.session = requests.Session()
        self.token = None
        self.logged_in = False

        # Rate limiting
        self.request_delay = 8.0  # seconds between requests (safe for 40/5min)
        self.last_request_time = 0

    def login(self) -> bool:
        """Login to Stockbit and get auth token."""
        if not self.username or not self.password:
            logger.error("Stockbit credentials not set. "
                         "Set STOCKBIT_USERNAME and STOCKBIT_PASSWORD env vars.")
            return False

        try:
            payload = {
                "username": self.username,
                "password": self.password,
            }
            headers = {
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            }

            resp = self.session.post(
                self.LOGIN_URL,
                json=payload,
                headers=headers,
                timeout=30,
            )

            if resp.status_code == 200:
                data = resp.json()
                # Stockbit returns token in response or sets cookies
                self.token = data.get("data", {}).get("token", "")
                if not self.token:
                    # Try getting from cookies
                    self.token = self.session.cookies.get("access_token", "")

                if self.token:
                    self.session.headers.update({
                        "Authorization": f"Bearer {self.token}",
                    })
                    self.logged_in = True
                    logger.info("Successfully logged into Stockbit")
                    return True
                else:
                    logger.warning("Login succeeded but no token found. "
                                   "Trying session cookies...")
                    # Some Stockbit versions use session cookies
                    self.logged_in = True
                    return True
            else:
                logger.error(f"Stockbit login failed: HTTP {resp.status_code}")
                return False

        except Exception as e:
            logger.error(f"Stockbit login error: {e}")
            return False

    def _rate_limit(self):
        """Enforce rate limiting between requests."""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.request_delay:
            time.sleep(self.request_delay - elapsed)
        self.last_request_time = time.time()

    def fetch_broker_summary(
        self, ticker: str, target_date: str = None
    ) -> Optional[List[Dict]]:
        """
        Fetch broker summary for a stock on a given date.

        Args:
            ticker: Stock ticker (e.g. "BBCA")
            target_date: Date string "YYYY-MM-DD" or None for today

        Returns:
            List of broker records or None on failure.
            Each record: {broker_code, buy_vol, sell_vol, buy_val, sell_val, net_val, net_vol}
        """
        if not self.logged_in:
            logger.error("Not logged in. Call login() first.")
            return None

        self._rate_limit()

        try:
            # Stockbit broker summary endpoint
            url = f"{self.BROKER_SUMMARY_URL}/{ticker}"
            params = {}
            if target_date:
                params["date"] = target_date

            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "application/json",
            }
            if self.token:
                headers["Authorization"] = f"Bearer {self.token}"

            resp = self.session.get(url, params=params, headers=headers, timeout=30)

            if resp.status_code == 200:
                data = resp.json()
                return self._parse_broker_summary(data, ticker)
            elif resp.status_code == 429:
                logger.warning(f"Rate limited on {ticker}. Waiting 60s...")
                time.sleep(60)
                return self.fetch_broker_summary(ticker, target_date)
            else:
                logger.warning(f"Failed to fetch broker summary for {ticker}: "
                               f"HTTP {resp.status_code}")
                return None

        except Exception as e:
            logger.error(f"Error fetching broker summary for {ticker}: {e}")
            return None

    def _parse_broker_summary(self, data: dict, ticker: str) -> List[Dict]:
        """
        Parse the Stockbit broker summary response.

        Stockbit typically returns data in format:
        {
            "data": {
                "broker_summary": {
                    "buyer": [
                        {"broker_code": "CC", "lot": 1234, "val": 5678000, "avg": 460},
                        ...
                    ],
                    "seller": [
                        {"broker_code": "YP", "lot": 987, "val": 4321000, "avg": 437},
                        ...
                    ]
                }
            }
        }

        The exact format may vary. This parser handles multiple known formats.
        """
        brokers = {}

        try:
            # Try different response formats
            summary = None

            # Format 1: data.broker_summary
            if isinstance(data, dict):
                if "data" in data:
                    inner = data["data"]
                    if isinstance(inner, dict):
                        summary = inner.get("broker_summary", inner)
                elif "broker_summary" in data:
                    summary = data["broker_summary"]
                else:
                    summary = data

            if not summary:
                logger.debug(f"No broker summary data found for {ticker}")
                return []

            # Parse buyers
            buyers = summary.get("buyer", summary.get("buyers", []))
            if isinstance(buyers, list):
                for b in buyers:
                    code = b.get("broker_code", b.get("code", b.get("broker", "")))
                    if not code:
                        continue
                    code = code.strip().upper()
                    if code not in brokers:
                        brokers[code] = {
                            "broker_code": code,
                            "buy_vol": 0, "sell_vol": 0,
                            "buy_val": 0, "sell_val": 0,
                        }
                    brokers[code]["buy_vol"] = float(b.get("lot", b.get("volume", b.get("vol", 0))))
                    brokers[code]["buy_val"] = float(b.get("val", b.get("value", 0)))

            # Parse sellers
            sellers = summary.get("seller", summary.get("sellers", []))
            if isinstance(sellers, list):
                for s in sellers:
                    code = s.get("broker_code", s.get("code", s.get("broker", "")))
                    if not code:
                        continue
                    code = code.strip().upper()
                    if code not in brokers:
                        brokers[code] = {
                            "broker_code": code,
                            "buy_vol": 0, "sell_vol": 0,
                            "buy_val": 0, "sell_val": 0,
                        }
                    brokers[code]["sell_vol"] = float(s.get("lot", s.get("volume", s.get("vol", 0))))
                    brokers[code]["sell_val"] = float(s.get("val", s.get("value", 0)))

        except Exception as e:
            logger.error(f"Error parsing broker summary for {ticker}: {e}")
            return []

        # Compute net values and classify
        result = []
        for code, b in brokers.items():
            b["net_val"] = b["buy_val"] - b["sell_val"]
            b["net_vol"] = b["buy_vol"] - b["sell_vol"]
            b["is_foreign"] = code in FOREIGN_BROKERS
            b["is_institutional"] = code in INSTITUTIONAL_BROKERS
            result.append(b)

        return result

    def scrape_and_store(
        self,
        session,  # SQLAlchemy session
        tickers: List[str],
        target_date: str = None,
    ) -> Dict[str, int]:
        """
        Scrape broker summary for multiple tickers and store in database.

        Returns dict of ticker → number of broker records stored.
        """
        from database.schema import BrokerSummary

        if not self.logged_in:
            if not self.login():
                return {}

        if target_date is None:
            target_date = date.today().isoformat()

        parse_date = datetime.strptime(target_date, "%Y-%m-%d").date()

        results = {}
        total = len(tickers)

        for i, ticker in enumerate(tickers):
            logger.info(f"[{i+1}/{total}] Fetching broker summary for {ticker}...")

            broker_data = self.fetch_broker_summary(ticker, target_date)

            if broker_data is None:
                results[ticker] = 0
                continue

            count = 0
            for b in broker_data:
                try:
                    existing = (
                        session.query(BrokerSummary)
                        .filter_by(
                            ticker=ticker,
                            date=parse_date,
                            broker_code=b["broker_code"],
                        )
                        .first()
                    )

                    if existing:
                        existing.buy_value = b["buy_val"]
                        existing.sell_value = b["sell_val"]
                        existing.buy_volume = b["buy_vol"]
                        existing.sell_volume = b["sell_vol"]
                        existing.net_value = b["net_val"]
                        existing.net_volume = b["net_vol"]
                    else:
                        bs = BrokerSummary(
                            ticker=ticker,
                            date=parse_date,
                            broker_code=b["broker_code"],
                            buy_value=b["buy_val"],
                            sell_value=b["sell_val"],
                            buy_volume=b["buy_vol"],
                            sell_volume=b["sell_vol"],
                            net_value=b["net_val"],
                            net_volume=b["net_vol"],
                        )
                        session.add(bs)
                    count += 1

                except Exception as e:
                    logger.error(f"Error storing broker data for {ticker}/{b['broker_code']}: {e}")

            session.commit()
            results[ticker] = count
            logger.info(f"  {ticker}: stored {count} broker records")

        return results

    def scrape_historical(
        self,
        session,  # SQLAlchemy session
        tickers: List[str],
        start_date: str,
        end_date: str = None,
        skip_weekends: bool = True,
        skip_existing: bool = True,
    ) -> Dict[str, int]:
        """
        Scrape HISTORICAL broker summary for backtesting.

        Iterates through every trading day from start_date to end_date
        and fetches broker summary for each ticker on each day.

        Args:
            session: SQLAlchemy database session
            tickers: List of stock tickers to scrape
            start_date: "YYYY-MM-DD" start date
            end_date: "YYYY-MM-DD" end date (default: yesterday)
            skip_weekends: Skip Saturday/Sunday
            skip_existing: Skip dates that already have data in DB

        Returns:
            Dict of ticker → total broker records stored

        WARNING: This is slow. For 100 tickers × 250 trading days = 25,000 API calls.
        At 8 seconds per call, that's ~56 hours.
        Recommendation: Run overnight via GitHub Actions, or scrape in batches.

        Example usage:
            scraper = StockbitBrokerScraper()
            scraper.login()
            # Scrape 3 months of data for LQ45
            scraper.scrape_historical(
                session, LQ45_TICKERS,
                start_date="2024-10-01",
                end_date="2024-12-31"
            )
        """
        from database.schema import BrokerSummary

        if not self.logged_in:
            if not self.login():
                return {}

        if end_date is None:
            end_date = (date.today() - timedelta(days=1)).isoformat()

        start = datetime.strptime(start_date, "%Y-%m-%d").date()
        end = datetime.strptime(end_date, "%Y-%m-%d").date()

        # Build list of trading days
        trading_days = []
        current = start
        while current <= end:
            if skip_weekends and current.weekday() >= 5:
                current += timedelta(days=1)
                continue
            trading_days.append(current)
            current += timedelta(days=1)

        total_days = len(trading_days)
        total_tickers = len(tickers)
        total_requests = total_days * total_tickers
        est_hours = (total_requests * self.request_delay) / 3600

        logger.info(
            f"Historical scrape: {total_tickers} tickers × {total_days} days "
            f"= {total_requests} requests (~{est_hours:.1f} hours)"
        )

        results = {t: 0 for t in tickers}

        for day_idx, trading_date in enumerate(trading_days):
            date_str = trading_date.isoformat()
            logger.info(
                f"--- Day {day_idx+1}/{total_days}: {date_str} ---"
            )

            for ticker_idx, ticker in enumerate(tickers):
                # Skip if data already exists for this ticker+date
                if skip_existing:
                    existing_count = (
                        session.query(BrokerSummary)
                        .filter_by(ticker=ticker, date=trading_date)
                        .count()
                    )
                    if existing_count > 0:
                        logger.debug(
                            f"  Skipping {ticker} {date_str} — "
                            f"{existing_count} records already exist"
                        )
                        continue

                broker_data = self.fetch_broker_summary(ticker, date_str)

                if broker_data is None or len(broker_data) == 0:
                    continue

                count = 0
                for b in broker_data:
                    try:
                        bs = BrokerSummary(
                            ticker=ticker,
                            date=trading_date,
                            broker_code=b["broker_code"],
                            buy_value=b["buy_val"],
                            sell_value=b["sell_val"],
                            buy_volume=b["buy_vol"],
                            sell_volume=b["sell_vol"],
                            net_value=b["net_val"],
                            net_volume=b["net_vol"],
                        )
                        session.merge(bs)
                        count += 1
                    except Exception as e:
                        logger.error(
                            f"Error storing {ticker}/{b['broker_code']}/{date_str}: {e}"
                        )

                session.commit()
                results[ticker] = results.get(ticker, 0) + count

                # Progress logging every 10 tickers
                if (ticker_idx + 1) % 10 == 0:
                    progress = ((day_idx * total_tickers + ticker_idx + 1)
                                / total_requests * 100)
                    logger.info(
                        f"  Progress: {progress:.1f}% "
                        f"({ticker_idx+1}/{total_tickers} tickers on {date_str})"
                    )

        total_records = sum(results.values())
        logger.info(
            f"Historical scrape complete: {total_records} broker records "
            f"across {total_tickers} tickers"
        )
        return results

    def compute_real_foreign_flow(
        self, session, ticker: str, target_date: str = None
    ) -> Optional[Dict]:
        """
        Compute REAL foreign flow from broker summary data.

        This replaces the synthetic estimation — uses actual broker codes
        to determine net foreign buying/selling.

        Returns:
            {net_foreign_value, net_foreign_volume, foreign_buy_value,
             foreign_sell_value, top_foreign_buyers, top_foreign_sellers}
        """
        from database.schema import BrokerSummary

        if target_date is None:
            target_date = date.today().isoformat()

        parse_date = datetime.strptime(target_date, "%Y-%m-%d").date()

        records = (
            session.query(BrokerSummary)
            .filter_by(ticker=ticker, date=parse_date)
            .all()
        )

        if not records:
            return None

        foreign_buy_val = 0
        foreign_sell_val = 0
        foreign_buy_vol = 0
        foreign_sell_vol = 0
        top_buyers = []
        top_sellers = []

        for r in records:
            if r.broker_code in FOREIGN_BROKERS:
                foreign_buy_val += r.buy_value
                foreign_sell_val += r.sell_value
                foreign_buy_vol += r.buy_volume
                foreign_sell_vol += r.sell_volume

                if r.net_value > 0:
                    top_buyers.append((r.broker_code, r.net_value))
                elif r.net_value < 0:
                    top_sellers.append((r.broker_code, abs(r.net_value)))

        top_buyers.sort(key=lambda x: x[1], reverse=True)
        top_sellers.sort(key=lambda x: x[1], reverse=True)

        return {
            "net_foreign_value": foreign_buy_val - foreign_sell_val,
            "net_foreign_volume": foreign_buy_vol - foreign_sell_vol,
            "foreign_buy_value": foreign_buy_val,
            "foreign_sell_value": foreign_sell_val,
            "top_foreign_buyers": top_buyers[:5],
            "top_foreign_sellers": top_sellers[:5],
        }

    def compute_institutional_flow(
        self, session, ticker: str, target_date: str = None
    ) -> Optional[Dict]:
        """
        Compute net institutional flow (foreign + domestic institutional).
        This gives the broadest "smart money" signal.
        """
        from database.schema import BrokerSummary

        if target_date is None:
            target_date = date.today().isoformat()

        parse_date = datetime.strptime(target_date, "%Y-%m-%d").date()

        records = (
            session.query(BrokerSummary)
            .filter_by(ticker=ticker, date=parse_date)
            .all()
        )

        if not records:
            return None

        smart_money_codes = FOREIGN_BROKERS | INSTITUTIONAL_BROKERS
        inst_buy = 0
        inst_sell = 0

        for r in records:
            if r.broker_code in smart_money_codes:
                inst_buy += r.buy_value
                inst_sell += r.sell_value

        return {
            "net_institutional_value": inst_buy - inst_sell,
            "institutional_buy_value": inst_buy,
            "institutional_sell_value": inst_sell,
        }
