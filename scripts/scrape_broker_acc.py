#!/usr/bin/env python3
"""
Daily Broker Accumulation Scraper
===================================
Scrapes today's Asing broker summary for all 137 IDX tickers from Stockbit,
computes rolling top_broker_acc and accumulation_score metrics,
and saves them to:
  broker_acc_daily.csv  — pre-computed metrics (append-only, used by signal pipeline)
  broker_raw_daily.csv  — raw per-broker net values (20-day rolling buffer for recompute)

Run daily before the signal pipeline:
  python scripts/scrape_broker_acc.py

Requires STOCKBIT_SESSION env var (GitHub Secret) or scripts/stockbit_session.json locally.

Rolling metrics match data_loader.py:load_broker_accumulation_df() exactly:
  accumulation_score: 5-day rolling count(accumulating Asing brokers) - count(distributing)
  top_broker_acc:     10-day rolling sum of net_value for top-5 Asing brokers by activity
"""

import logging
import sys
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))

from scraper.stockbit_auth import get_stockbit_token
from scraper.broker_scraper import StockbitBrokerScraper
from scraper.price_scraper import LQ45_TICKERS

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).parent.parent
RAW_CSV = REPO_ROOT / "broker_raw_daily.csv"
ACC_CSV = REPO_ROOT / "broker_acc_daily.csv"
RAW_KEEP_DAYS = 20  # rolling buffer depth (>= 10-day window needed for top_broker_acc)


def compute_broker_metrics(raw_df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute accumulation_score and top_broker_acc from raw broker data.

    Replicates database/data_loader.py:load_broker_accumulation_df() exactly.

    Args:
        raw_df: DataFrame with columns [date, ticker, broker_code, net_value]
                (Asing brokers only, date already parsed as datetime)

    Returns:
        DataFrame with columns [date, ticker, accumulation_score, top_broker_acc]
    """
    results = []

    for ticker, tdf in raw_df.groupby("ticker"):
        tdf = tdf.sort_values("date")

        # Pivot: rows=date, columns=broker_code, values=net_value (NaN = no trade)
        pivot = tdf.pivot_table(
            index="date", columns="broker_code", values="net_value", aggfunc="sum"
        )
        if pivot.empty:
            continue

        # ── accumulation_score (5-day rolling) ──────────────────────────────
        is_buy = (pivot > 0).astype(float).where(pivot.notna())
        is_active = pivot.notna().astype(float)
        buy_days = is_buy.rolling(5, min_periods=1).sum()
        active_days = is_active.rolling(5, min_periods=1).sum()
        accumulating = (active_days >= 3) & (buy_days >= 4)
        distributing = (active_days >= 3) & (buy_days <= 1)
        score = accumulating.sum(axis=1) - distributing.sum(axis=1)

        # ── top_broker_acc (10-day rolling, top-5 by activity) ──────────────
        top_n = 5
        window = 10
        filled = pivot.fillna(0)
        rolling_net = filled.rolling(window, min_periods=3).sum()
        rolling_abs = filled.abs().rolling(window, min_periods=3).sum()

        top_scores = []
        for d in rolling_net.index:
            abs_row = rolling_abs.loc[d]
            net_row = rolling_net.loc[d]
            active = abs_row[abs_row > 0]
            if len(active) == 0:
                top_scores.append(0.0)
            else:
                top_brokers = active.nlargest(min(top_n, len(active))).index
                top_scores.append(float(net_row[top_brokers].sum()))

        results.append(pd.DataFrame({
            "date": score.index,
            "ticker": ticker,
            "accumulation_score": score.values,
            "top_broker_acc": top_scores,
        }))

    if not results:
        return pd.DataFrame(columns=["date", "ticker", "accumulation_score", "top_broker_acc"])
    return pd.concat(results, ignore_index=True)


def main():
    today = date.today()
    today_str = today.isoformat()
    logger.info(f"=== Broker scrape for {today_str} ({len(LQ45_TICKERS)} tickers) ===")

    # ── 1. Get token ─────────────────────────────────────────────────────────
    token = get_stockbit_token()
    if not token:
        logger.error(
            "No valid Stockbit token. "
            "Re-run scripts/setup_stockbit_session.py to refresh the session."
        )
        sys.exit(1)

    # ── 2. Scrape Asing broker data for all tickers ──────────────────────────
    scraper = StockbitBrokerScraper(token=token)
    if not scraper.login():
        logger.error("Authentication failed.")
        sys.exit(1)

    new_rows = []
    failed = []

    for i, ticker in enumerate(LQ45_TICKERS):
        logger.info(f"[{i+1}/{len(LQ45_TICKERS)}] {ticker}")
        data = scraper.fetch_broker_summary(ticker, today_str)
        if data is None:
            failed.append(ticker)
            continue
        for b in data.get("brokers", []):
            if b.get("is_foreign"):
                new_rows.append({
                    "date": today_str,
                    "ticker": ticker,
                    "broker_code": b["code"],
                    "net_value": b["net_val"],
                })

    if failed:
        logger.warning(f"Failed to fetch {len(failed)} tickers: {failed[:10]}{'...' if len(failed)>10 else ''}")

    if not new_rows:
        logger.warning("No broker data fetched today (market may be closed or all requests failed).")
        sys.exit(0)

    logger.info(f"Fetched {len(new_rows)} Asing broker rows across {len(set(r['ticker'] for r in new_rows))} tickers.")

    # ── 3. Update rolling raw buffer ─────────────────────────────────────────
    today_df = pd.DataFrame(new_rows)
    today_df["date"] = pd.to_datetime(today_df["date"])

    if RAW_CSV.exists():
        existing_raw = pd.read_csv(RAW_CSV, parse_dates=["date"])
        # Remove today's rows first (idempotent — safe to re-run)
        existing_raw = existing_raw[existing_raw["date"].dt.date != today]
        raw_df = pd.concat([existing_raw, today_df], ignore_index=True)
    else:
        raw_df = today_df

    # Trim to last RAW_KEEP_DAYS calendar days
    cutoff = pd.Timestamp(today - timedelta(days=RAW_KEEP_DAYS))
    raw_df = raw_df[raw_df["date"] >= cutoff]
    raw_df.to_csv(RAW_CSV, index=False)
    logger.info(f"broker_raw_daily.csv: {len(raw_df)} rows across {raw_df['date'].nunique()} trading days")

    # ── 4. Compute rolling metrics ────────────────────────────────────────────
    metrics_df = compute_broker_metrics(raw_df)
    today_metrics = metrics_df[metrics_df["date"].dt.date == today]

    if today_metrics.empty:
        logger.warning("Could not compute metrics for today.")
        sys.exit(0)

    logger.info(
        f"Computed metrics for {len(today_metrics)} tickers. "
        f"top_broker_acc range: [{today_metrics['top_broker_acc'].min():.0f}, "
        f"{today_metrics['top_broker_acc'].max():.0f}]"
    )

    # ── 5. Append to broker_acc_daily.csv ────────────────────────────────────
    if ACC_CSV.exists():
        existing_acc = pd.read_csv(ACC_CSV, parse_dates=["date"])
        existing_acc = existing_acc[existing_acc["date"].dt.date != today]
        acc_df = pd.concat([existing_acc, today_metrics], ignore_index=True)
    else:
        acc_df = today_metrics

    acc_df.to_csv(ACC_CSV, index=False)
    logger.info(
        f"broker_acc_daily.csv: {len(acc_df)} rows, "
        f"latest date: {pd.to_datetime(acc_df['date']).max().date()}"
    )
    logger.info("Done.")


if __name__ == "__main__":
    main()
