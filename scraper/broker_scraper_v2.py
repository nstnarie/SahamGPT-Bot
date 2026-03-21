"""
Stockbit Broker Summary Scraper v2
====================================
Scrapes broker summary from Stockbit's marketdetectors API.

Exact API endpoint (confirmed from browser DevTools):
  GET https://exodus.stockbit.com/marketdetectors/{TICKER}
      ?from=YYYY-MM-DD
      &to=YYYY-MM-DD
      &transaction_type=TRANSACTION_TYPE_NET
      &market_board=MARKET_BOARD_REGULER
      &investor_type=INVESTOR_TYPE_ALL
      &limit=25

Response contains:
  - data.broker_summary.brokers_buy[] — net buyers
  - data.broker_summary.brokers_sell[] — net sellers
  - Each broker has: netbs_broker_code, type (Asing/Lokal/Pemerintah),
    blot/slot (net lots), bval/sval (net value), freq

The "type" field is KEY:
  - "Asing" = Foreign broker → this is the institutional signal
  - "Pemerintah" = Government/SOE broker
  - "Lokal" = Local/retail broker

Required GitHub Secrets:
  - STOCKBIT_USERNAME
  - STOCKBIT_PASSWORD
"""

import logging
import os
import time
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional

import requests

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────
# BROKER CLASSIFICATION (from Stockbit's own "type" field)
# ──────────────────────────────────────────────────────────────
# We now use Stockbit's built-in classification:
#   "Asing" = Foreign
#   "Pemerintah" = Government/SOE institutional
#   "Lokal" = Local (mix of retail and domestic institutional)
#
# But we also keep a manual list of known institutional locals
# that trade large blocks (not retail despite "Lokal" label)

KNOWN_INSTITUTIONAL_LOCALS = {
    "GR",  # Trimegah — large block trader
    "PD",  # CGS-CIMB — institutional flow
    "SQ",  # Shinhan Sekuritas
    "LG",  # Bahana Sekuritas
    "BB",  # Sucor Sekuritas — institutional
}


class StockbitBrokerScraper:
    """Scrapes broker summary from Stockbit's marketdetectors API."""

    BASE_URL = "https://exodus.stockbit.com"
    LOGIN_URL = f"{BASE_URL}/login"
    MARKET_DETECTORS_URL = f"{BASE_URL}/marketdetectors"

    def __init__(self, username: str = None, password: str = None):
        self.username = username or os.getenv("STOCKBIT_USERNAME", "")
        self.password = password or os.getenv("STOCKBIT_PASSWORD", "")
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json",
        })
        self.logged_in = False
        self.request_delay = 8.0  # safe for 40 req / 5 min
        self.last_request_time = 0

    # ──────────────────────────────────────────────────────────
    # AUTH
    # ──────────────────────────────────────────────────────────

    def login(self) -> bool:
        """Login to Stockbit and establish session."""
        if not self.username or not self.password:
            logger.error("Set STOCKBIT_USERNAME and STOCKBIT_PASSWORD env vars")
            return False

        try:
            resp = self.session.post(
                self.LOGIN_URL,
                json={"username": self.username, "password": self.password},
                timeout=30,
            )

            if resp.status_code == 200:
                data = resp.json()
                token = data.get("data", {}).get("token", "")
                if token:
                    self.session.headers["Authorization"] = f"Bearer {token}"
                self.logged_in = True
                logger.info("Logged into Stockbit successfully")
                return True
            else:
                logger.error(f"Login failed: HTTP {resp.status_code}")
                return False

        except Exception as e:
            logger.error(f"Login error: {e}")
            return False

    # ──────────────────────────────────────────────────────────
    # FETCH BROKER SUMMARY
    # ──────────────────────────────────────────────────────────

    def _rate_limit(self):
        elapsed = time.time() - self.last_request_time
        if elapsed < self.request_delay:
            time.sleep(self.request_delay - elapsed)
        self.last_request_time = time.time()

    def fetch_broker_summary(
        self, ticker: str, from_date: str, to_date: str = None
    ) -> Optional[Dict]:
        """
        Fetch broker summary for a ticker over a date range.

        Args:
            ticker: e.g. "BBCA"
            from_date: "YYYY-MM-DD"
            to_date: "YYYY-MM-DD" (default = same as from_date for single day)

        Returns:
            Parsed dict with foreign/local/institutional flows, or None.
        """
        if not self.logged_in:
            logger.error("Not logged in")
            return None

        if to_date is None:
            to_date = from_date

        self._rate_limit()

        try:
            url = f"{self.MARKET_DETECTORS_URL}/{ticker}"
            params = {
                "from": from_date,
                "to": to_date,
                "transaction_type": "TRANSACTION_TYPE_NET",
                "market_board": "MARKET_BOARD_REGULER",
                "investor_type": "INVESTOR_TYPE_ALL",
                "limit": 50,  # get all brokers
            }

            resp = self.session.get(url, params=params, timeout=30)

            if resp.status_code == 200:
                data = resp.json()
                return self._parse_response(data, ticker, from_date)
            elif resp.status_code == 429:
                logger.warning(f"Rate limited on {ticker}. Waiting 60s...")
                time.sleep(60)
                return self.fetch_broker_summary(ticker, from_date, to_date)
            else:
                logger.warning(f"{ticker}: HTTP {resp.status_code}")
                return None

        except Exception as e:
            logger.error(f"Error fetching {ticker}: {e}")
            return None

    def _parse_response(self, raw: dict, ticker: str, date_str: str) -> Dict:
        """
        Parse the Stockbit marketdetectors response.

        Returns dict with:
          - brokers: list of {code, type, net_lot, net_val, buy_val, sell_val, freq}
          - foreign_net_val: total net value from "Asing" brokers
          - foreign_net_lot: total net lots from "Asing" brokers
          - govt_net_val: total net from "Pemerintah" brokers
          - local_net_val: total net from "Lokal" brokers
          - bandar_detector: accumulation/distribution summary
        """
        result = {
            "ticker": ticker,
            "date": date_str,
            "brokers": [],
            "foreign_net_val": 0,
            "foreign_net_lot": 0,
            "govt_net_val": 0,
            "govt_net_lot": 0,
            "local_net_val": 0,
            "local_net_lot": 0,
            "institutional_net_val": 0,
            "bandar_accdist": "",
            "total_value": 0,
        }

        try:
            data = raw.get("data", {})

            # Bandar detector summary
            bd = data.get("bandar_detector", {})
            result["bandar_accdist"] = bd.get("broker_accdist", "")
            result["total_value"] = float(bd.get("value", 0))

            # Parse broker summary
            bs = data.get("broker_summary", {})

            # Buyers (positive net)
            for b in bs.get("brokers_buy", []):
                broker = self._parse_broker_record(b, side="buy")
                if broker:
                    result["brokers"].append(broker)
                    self._accumulate_flow(result, broker)

            # Sellers (negative net)
            for s in bs.get("brokers_sell", []):
                broker = self._parse_broker_record(s, side="sell")
                if broker:
                    result["brokers"].append(broker)
                    self._accumulate_flow(result, broker)

            # Institutional = Foreign + Government + known institutional locals
            result["institutional_net_val"] = (
                result["foreign_net_val"]
                + result["govt_net_val"]
            )

        except Exception as e:
            logger.error(f"Parse error for {ticker}: {e}")

        return result

    def _parse_broker_record(self, rec: dict, side: str) -> Optional[Dict]:
        """Parse a single broker buy/sell record from Stockbit response."""
        try:
            code = rec.get("netbs_broker_code", "")
            if not code:
                return None

            broker_type = rec.get("type", "Lokal")  # Asing / Lokal / Pemerintah
            freq = int(float(rec.get("freq", 0)))

            if side == "buy":
                net_lot = int(float(rec.get("blot", 0)))
                net_val = float(rec.get("bval", 0))
                # blotv/bvalv are total volumes (buy+sell combined)
                total_val = float(rec.get("bvalv", 0))
                buy_val = (total_val + abs(net_val)) / 2
                sell_val = (total_val - abs(net_val)) / 2
            else:
                net_lot = int(float(rec.get("slot", 0)))  # already negative
                net_val = float(rec.get("sval", 0))  # already negative
                total_val = float(rec.get("svalv", 0))
                sell_val = (total_val + abs(net_val)) / 2
                buy_val = (total_val - abs(net_val)) / 2

            return {
                "code": code,
                "type": broker_type,
                "net_lot": net_lot,
                "net_val": net_val,
                "buy_val": max(buy_val, 0),
                "sell_val": max(sell_val, 0),
                "freq": freq,
                "is_foreign": broker_type == "Asing",
                "is_govt": broker_type == "Pemerintah",
                "is_institutional_local": code in KNOWN_INSTITUTIONAL_LOCALS,
            }

        except Exception as e:
            logger.debug(f"Error parsing broker record: {e}")
            return None

    def _accumulate_flow(self, result: dict, broker: dict):
        """Add broker's flow to the appropriate category total."""
        if broker["is_foreign"]:
            result["foreign_net_val"] += broker["net_val"]
            result["foreign_net_lot"] += broker["net_lot"]
        elif broker["is_govt"]:
            result["govt_net_val"] += broker["net_val"]
            result["govt_net_lot"] += broker["net_lot"]
        else:
            result["local_net_val"] += broker["net_val"]
            result["local_net_lot"] += broker["net_lot"]

    # ──────────────────────────────────────────────────────────
    # STORE TO DATABASE
    # ──────────────────────────────────────────────────────────

    def scrape_and_store(
        self, session, tickers: List[str], target_date: str = None
    ) -> Dict[str, int]:
        """Scrape today's broker summary and store in database."""
        from database.schema import BrokerSummary

        if not self.logged_in and not self.login():
            return {}

        if target_date is None:
            target_date = date.today().isoformat()

        parse_date = datetime.strptime(target_date, "%Y-%m-%d").date()
        results = {}

        for i, ticker in enumerate(tickers):
            logger.info(f"[{i+1}/{len(tickers)}] {ticker}...")

            data = self.fetch_broker_summary(ticker, target_date)
            if data is None:
                results[ticker] = 0
                continue

            count = 0
            for b in data["brokers"]:
                try:
                    existing = (
                        session.query(BrokerSummary)
                        .filter_by(
                            ticker=ticker, date=parse_date,
                            broker_code=b["code"],
                        )
                        .first()
                    )

                    if existing:
                        existing.broker_type = b.get("type", "")
                        existing.buy_value = b["buy_val"]
                        existing.sell_value = b["sell_val"]
                        existing.buy_volume = abs(b["net_lot"]) if b["net_lot"] > 0 else 0
                        existing.sell_volume = abs(b["net_lot"]) if b["net_lot"] < 0 else 0
                        existing.net_value = b["net_val"]
                        existing.net_volume = b["net_lot"]
                    else:
                        bs = BrokerSummary(
                            ticker=ticker, date=parse_date,
                            broker_code=b["code"],
                            broker_type=b.get("type", ""),
                            buy_value=b["buy_val"],
                            sell_value=b["sell_val"],
                            buy_volume=abs(b["net_lot"]) if b["net_lot"] > 0 else 0,
                            sell_volume=abs(b["net_lot"]) if b["net_lot"] < 0 else 0,
                            net_value=b["net_val"],
                            net_volume=b["net_lot"],
                        )
                        session.add(bs)
                    count += 1
                except Exception as e:
                    logger.error(f"Store error {ticker}/{b['code']}: {e}")

            session.commit()
            results[ticker] = count

        return results

    # ──────────────────────────────────────────────────────────
    # HISTORICAL BACKFILL
    # ──────────────────────────────────────────────────────────

    def scrape_historical(
        self, session, tickers: List[str],
        start_date: str, end_date: str = None,
        skip_weekends: bool = True,
        skip_existing: bool = True,
    ) -> Dict[str, int]:
        """
        Scrape historical broker summary for backtesting.

        Loops through every trading day from start_date to end_date.
        Uses single-day requests (from=to) for per-day granularity.

        Rate limit: ~8 sec/request. For 100 tickers × 250 days = ~56 hours.
        Use the batch workflow to split across multiple runs.

        Args:
            session: SQLAlchemy session
            tickers: List of tickers
            start_date: "YYYY-MM-DD"
            end_date: "YYYY-MM-DD" (default: yesterday)
            skip_weekends: Skip Sat/Sun
            skip_existing: Skip ticker+date combos already in DB

        Returns:
            Dict of ticker → total records stored
        """
        from database.schema import BrokerSummary

        if not self.logged_in and not self.login():
            return {}

        if end_date is None:
            end_date = (date.today() - timedelta(days=1)).isoformat()

        start = datetime.strptime(start_date, "%Y-%m-%d").date()
        end = datetime.strptime(end_date, "%Y-%m-%d").date()

        # Build trading days
        trading_days = []
        current = start
        while current <= end:
            if not (skip_weekends and current.weekday() >= 5):
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
            logger.info(f"--- Day {day_idx+1}/{total_days}: {date_str} ---")

            for ticker_idx, ticker in enumerate(tickers):
                # Skip if already in DB
                if skip_existing:
                    existing = (
                        session.query(BrokerSummary)
                        .filter_by(ticker=ticker, date=trading_date)
                        .count()
                    )
                    if existing > 0:
                        continue

                # Fetch single day (from=to)
                data = self.fetch_broker_summary(ticker, date_str, date_str)

                if data is None or len(data.get("brokers", [])) == 0:
                    continue

                count = 0
                for b in data["brokers"]:
                    try:
                        bs = BrokerSummary(
                            ticker=ticker, date=trading_date,
                            broker_code=b["code"],
                            broker_type=b.get("type", ""),
                            buy_value=b["buy_val"],
                            sell_value=b["sell_val"],
                            buy_volume=abs(b["net_lot"]) if b["net_lot"] > 0 else 0,
                            sell_volume=abs(b["net_lot"]) if b["net_lot"] < 0 else 0,
                            net_value=b["net_val"],
                            net_volume=b["net_lot"],
                        )
                        session.merge(bs)
                        count += 1
                    except Exception as e:
                        logger.error(f"Store error {ticker}/{b['code']}/{date_str}: {e}")

                session.commit()
                results[ticker] = results.get(ticker, 0) + count

                # Progress log
                if (ticker_idx + 1) % 10 == 0:
                    progress = (day_idx * total_tickers + ticker_idx + 1) / total_requests * 100
                    logger.info(f"  Progress: {progress:.1f}%")

        total_records = sum(results.values())
        logger.info(f"Done: {total_records} records across {total_tickers} tickers")
        return results

    # ──────────────────────────────────────────────────────────
    # COMPUTE REAL FOREIGN FLOW FROM STORED DATA
    # ──────────────────────────────────────────────────────────

    def compute_foreign_flow_from_db(
        self, session, ticker: str, target_date: str
    ) -> Optional[Dict]:
        """
        Compute real foreign flow from stored broker summary data.
        Uses the broker_type field stored from Stockbit's API response.
        """
        from database.schema import BrokerSummary

        parse_date = datetime.strptime(target_date, "%Y-%m-%d").date()

        records = (
            session.query(BrokerSummary)
            .filter_by(ticker=ticker, date=parse_date)
            .all()
        )

        if not records:
            return None

        foreign_net_val = 0
        foreign_net_vol = 0
        govt_net_val = 0

        for r in records:
            btype = (r.broker_type or "").strip()
            if btype == "Asing":
                foreign_net_val += r.net_value
                foreign_net_vol += r.net_volume
            elif btype == "Pemerintah":
                govt_net_val += r.net_value
            # If broker_type is empty (old data), fall back to code list
            elif not btype and r.broker_code in _ALL_FOREIGN_CODES:
                foreign_net_val += r.net_value
                foreign_net_vol += r.net_volume

        return {
            "net_foreign_value": foreign_net_val,
            "net_foreign_volume": foreign_net_vol,
            "net_govt_value": govt_net_val,
            "net_institutional_value": foreign_net_val + govt_net_val,
        }


# Known foreign broker codes (from Stockbit "Asing" type)
# This list is based on commonly seen foreign brokers on IDX
_ALL_FOREIGN_CODES = {
    # Major foreign
    "AK", "BK", "YU", "RX", "KZ", "TP", "ZP",
    "YP", "KK", "DR", "DX", "BQ", "XA", "AG",
    "LS", "AI", "RB", "CP", "OD", "GI", "DP",
    # These appear as "Asing" in the sample response
    # Keep this list updated based on actual API responses
}

# Note: The BEST approach is to store the "type" field from each API response
# alongside the broker record, so you don't need to maintain this list manually.
# Consider adding a "broker_type" column to the BrokerSummary table.
