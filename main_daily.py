#!/usr/bin/env python3
"""
main_daily.py — Automated Daily Pipeline
==========================================

Runs automatically after IDX market close:
  1. Scrape latest market data
  2. Compute signals for all stocks
  3. Rank top 5 by composite score
  4. Generate AI reasoning (via Claude API)
  5. Send to Telegram

Schedule this with cron to run at 16:30 WIB (after market close):
  30 16 * * 1-5 cd /path/to/idx_swing_trader && python main_daily.py

Or use the built-in scheduler (runs indefinitely):
  python main_daily.py --scheduler

Environment variables needed:
  TELEGRAM_BOT_TOKEN   — from @BotFather
  TELEGRAM_CHAT_ID     — your chat/group ID
  ANTHROPIC_API_KEY    — (optional) for AI reasoning

DISCLAIMER: For educational and research purposes only.
"""

import argparse
import json
import logging
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))

from config import FrameworkConfig, DATABASE_URL
from database.schema import create_all_tables, get_session, get_engine, Stock
from database.data_loader import (
    load_prices_as_dataframe, load_index_df, load_foreign_flow_df,
)
from scraper.price_scraper import PriceScraper, LQ45_TICKERS
from signals.signal_combiner import SignalCombiner
from signals.market_regime import MarketRegimeFilter
from notifications.telegram_notifier import (
    format_and_send_daily_report, send_telegram_message,
)


def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler("daily_pipeline.log", mode="a"),
        ],
    )


def run_daily_pipeline(
    tickers: List[str],
    db_url: str = DATABASE_URL,
    lookback_days: int = 300,
    top_n: int = 5,
) -> bool:
    """
    Execute the full daily pipeline.

    Returns True if successful, False on error.
    """
    logger = logging.getLogger("daily_pipeline")
    start_time = time.time()
    today = datetime.now().strftime("%Y-%m-%d")

    logger.info("=" * 50)
    logger.info(f"  DAILY PIPELINE — {today}")
    logger.info("=" * 50)

    config = FrameworkConfig()

    try:
        # ── 1. DATABASE ──
        engine = create_all_tables(db_url)
        session = get_session(engine)

        # ── 2. SCRAPE LATEST DATA ──
        logger.info(f"Scraping data for {len(tickers)} stocks...")
        lookback_start = (
            datetime.now() - timedelta(days=lookback_days)
        ).strftime("%Y-%m-%d")

        price_scraper = PriceScraper(config)
        price_scraper.scrape_and_store(session, tickers, start_date=lookback_start)

        logger.info("Data scraping complete.")

        # ── 3. LOAD DATA ──
        start_dt = pd.Timestamp(lookback_start).date()
        end_dt = pd.Timestamp(today).date()

        universe_prices: Dict[str, pd.DataFrame] = {}
        foreign_flows: Dict[str, pd.DataFrame] = {}

        for ticker in tickers:
            pdf = load_prices_as_dataframe(session, ticker, start_dt, end_dt)
            if not pdf.empty:
                universe_prices[ticker] = pdf
            ff = load_foreign_flow_df(session, ticker, start_dt, end_dt)
            if not ff.empty:
                foreign_flows[ticker] = ff

        ihsg_df = load_index_df(session, "IHSG", start_dt, end_dt)

        if not universe_prices:
            logger.error("No price data loaded. Aborting.")
            send_telegram_message(
                "⚠️ <b>IDX Pipeline Error</b>\nNo price data loaded today. "
                "Check data sources.",
                parse_mode="HTML",
            )
            return False

        # ── 4. COMPUTE SIGNALS ──
        logger.info("Computing signals...")
        combiner = SignalCombiner(config)

        # Load ff-price correlation ratios for the ff_corr entry filter (Step 18).
        # Blocks stocks where foreign flow genuinely drives the price (corr >= 0.30).
        ff_corr_path = Path(__file__).parent / "ff_corr_ratios.json"
        fp_ratios: Dict[str, float] = {}
        if ff_corr_path.exists():
            with open(ff_corr_path) as f:
                fp_ratios = json.load(f)
            logger.info(f"Loaded ff_corr_ratios for {len(fp_ratios)} tickers")
        else:
            logger.warning("ff_corr_ratios.json not found — ff_corr filter disabled")

        # Load pre-computed broker accumulation metrics (top_broker_acc, accumulation_score).
        # Scraped daily before signal generation via scripts/scrape_broker_acc.py.
        # If missing, BS/TBA and accumulation filters fall back to 0 (no effect).
        broker_data: Dict[str, pd.DataFrame] = {}
        broker_acc_path = Path(__file__).parent / "broker_acc_daily.csv"
        if broker_acc_path.exists():
            try:
                broker_acc_df = pd.read_csv(broker_acc_path, parse_dates=["date"])
                broker_acc_df = broker_acc_df.set_index("date")
                for ticker in tickers:
                    tdf = broker_acc_df[broker_acc_df["ticker"] == ticker][
                        ["accumulation_score", "top_broker_acc"]
                    ]
                    if not tdf.empty:
                        broker_data[ticker] = tdf
                logger.info(f"Loaded broker_acc_daily for {len(broker_data)} tickers")
            except Exception as e:
                logger.warning(f"Failed to load broker_acc_daily.csv: {e} — broker filters disabled")
        else:
            logger.warning("broker_acc_daily.csv not found — broker filters disabled")

        all_signals = combiner.generate_signals_universe(
            universe_prices, ihsg_df, foreign_flows,
            broker_data=broker_data, fp_ratios=fp_ratios,
        )

        # ── 5. MARKET REGIME ──
        regime_filter = MarketRegimeFilter(config.regime)
        regime, exposure = regime_filter.get_current_regime(
            ihsg_df, universe_prices
        )

        ihsg_close = None
        if not ihsg_df.empty:
            ihsg_close = ihsg_df["close"].iloc[-1]

        # ── 6. COLLECT TOP SIGNALS ──
        buy_signals = []
        sell_signals = []

        for ticker, sig_df in all_signals.items():
            if sig_df.empty:
                continue
            latest = sig_df.iloc[-1]

            signal_data = {
                "ticker": ticker,
                "close": latest.get("close", 0),
                "composite_score": latest.get("composite_score", 0),
                "rsi": latest.get("rsi", 50),
                "volume_ratio": latest.get("vol_ratio", 1.0),
                "foreign_score": latest.get("foreign_score", 0.5),
                "volume_price_score": latest.get("volume_price_score", 0.5),
                "broker_score": latest.get("broker_score", 0.5),
                "ema_50": latest.get("ema_50", 0),
                "macd_histogram": latest.get("macd_histogram", 0),
                "atr": latest.get("atr", 0),
            }

            if latest.get("signal") == "BUY":
                buy_signals.append(signal_data)
            elif latest.get("signal") == "SELL":
                sell_signals.append(signal_data)

        # Sort buys by composite score, take top N
        buy_signals.sort(key=lambda x: x["composite_score"], reverse=True)
        top_buys = buy_signals[:top_n]

        logger.info(
            f"Results: {len(buy_signals)} BUY, {len(sell_signals)} SELL signals. "
            f"Regime: {regime}. Sending top {len(top_buys)} to Telegram."
        )

        # ── 7. SEND TO TELEGRAM ──
        success = format_and_send_daily_report(
            buy_signals=top_buys,
            sell_signals=sell_signals,
            regime=regime,
            exposure=exposure,
            ihsg_close=ihsg_close,
        )

        elapsed = time.time() - start_time
        logger.info(f"Pipeline completed in {elapsed:.0f}s. Telegram: {'OK' if success else 'FAILED'}")

        session.close()
        return success

    except Exception as e:
        logger.exception(f"Pipeline failed: {e}")
        # Try to notify about the failure
        try:
            send_telegram_message(
                f"🚨 <b>IDX Pipeline Error</b>\n"
                f"<code>{str(e)[:500]}</code>",
                parse_mode="HTML",
            )
        except Exception:
            pass
        return False


# ──────────────────────────────────────────────────────────────
# BUILT-IN SCHEDULER
# ──────────────────────────────────────────────────────────────

def run_scheduler(
    tickers: List[str],
    db_url: str,
    run_hour: int = 16,
    run_minute: int = 30,
):
    """
    Simple built-in scheduler that runs the pipeline at the
    specified time (WIB) every weekday.

    For production, use cron or systemd instead.
    """
    import pytz

    logger = logging.getLogger("scheduler")
    wib = pytz.timezone("Asia/Jakarta")

    logger.info(
        f"Scheduler started. Will run daily at {run_hour:02d}:{run_minute:02d} WIB "
        f"(Mon-Fri)."
    )

    last_run_date = None

    while True:
        now = datetime.now(wib)

        # Only run on weekdays
        is_weekday = now.weekday() < 5  # Mon=0 ... Fri=4

        # Check if it's time to run
        is_run_time = (
            now.hour == run_hour
            and now.minute >= run_minute
            and now.minute < run_minute + 5  # 5-minute window
        )

        # Haven't run today yet
        not_run_today = last_run_date != now.date()

        if is_weekday and is_run_time and not_run_today:
            logger.info("⏰ Scheduled run triggered!")
            success = run_daily_pipeline(tickers, db_url)
            last_run_date = now.date()
            if success:
                logger.info("✅ Scheduled run completed successfully")
            else:
                logger.error("❌ Scheduled run failed")

        # Sleep 30 seconds before checking again
        time.sleep(30)


def main():
    parser = argparse.ArgumentParser(description="IDX Daily Pipeline")
    parser.add_argument("--tickers", nargs="+", default=None,
                        help="Tickers to scan (default: LQ45)")
    parser.add_argument("--db", default=DATABASE_URL)
    parser.add_argument("--top", type=int, default=5,
                        help="Number of top signals to send")
    parser.add_argument("--lookback-days", type=int, default=300)
    parser.add_argument("--scheduler", action="store_true",
                        help="Run as persistent scheduler (16:30 WIB weekdays)")
    parser.add_argument("--schedule-time", default="16:30",
                        help="Schedule time in HH:MM format (default: 16:30)")
    args = parser.parse_args()

    setup_logging()
    tickers = args.tickers or LQ45_TICKERS

    if args.scheduler:
        hour, minute = map(int, args.schedule_time.split(":"))
        run_scheduler(tickers, args.db, run_hour=hour, run_minute=minute)
    else:
        # Single run
        success = run_daily_pipeline(
            tickers=tickers,
            db_url=args.db,
            lookback_days=args.lookback_days,
            top_n=args.top,
        )
        sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
