#!/usr/bin/env python3
"""
main_backtest.py — Run the full IDX Swing Trading backtest
===========================================================

Usage:
    python main_backtest.py [--start 2021-01-01] [--end 2024-12-31] [--capital 1000000000]

DISCLAIMER: For educational and research purposes only.
Past performance does not guarantee future results.
"""

import argparse
import logging
import sys
from pathlib import Path
from typing import Dict

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))

from config import FrameworkConfig, DATABASE_URL
from database.schema import create_all_tables, get_session, get_engine, Stock
from database.data_loader import (
    load_prices_as_dataframe, load_index_df,
    load_foreign_flow_df, load_broker_summary_as_ff_df,
    load_broker_accumulation_df,
    data_quality_check,
)
from scraper.price_scraper import PriceScraper, LQ45_TICKERS
from scraper.flow_scraper import FundamentalScraper
from backtest.engine import BacktestEngine
from backtest.metrics import format_metrics_report
from reports.visualizer import generate_all_reports


def setup_logging(level: str = "INFO"):
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler("backtest_run.log", mode="w"),
        ],
    )


def parse_args():
    parser = argparse.ArgumentParser(description="IDX Swing Trader Backtest")
    parser.add_argument("--start", default="2021-01-01")
    parser.add_argument("--end", default="2024-12-31")
    parser.add_argument("--capital", type=float, default=1_000_000_000)
    parser.add_argument("--db", default=DATABASE_URL)
    parser.add_argument("--scrape", action="store_true",
                        help="Force re-scrape all data")
    parser.add_argument("--tickers", nargs="+", default=None)
    # --real-broker removed: real Asing broker data is now always used
    parser.add_argument("--output", default="reports")
    parser.add_argument("--log-level", default="INFO",
                        choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    return parser.parse_args()


def main():
    args = parse_args()
    setup_logging(args.log_level)
    logger = logging.getLogger("main_backtest")

    logger.info("=" * 60)
    logger.info("  IDX SWING TRADING FRAMEWORK — BACKTEST")
    logger.info(f"  Period: {args.start} to {args.end}")
    logger.info(f"  Capital: Rp {args.capital:,.0f}")
    logger.info("=" * 60)

    config = FrameworkConfig()
    config.backtest.start_date = args.start
    config.backtest.end_date = args.end
    config.backtest.initial_capital = args.capital

    tickers = args.tickers or LQ45_TICKERS
    logger.info(f"Universe: {len(tickers)} stocks")

    # Database
    engine = create_all_tables(args.db)
    session = get_session(engine)

    # Scrape if needed
    needs_scrape = args.scrape
    if not needs_scrape:
        sample_df = load_prices_as_dataframe(session, tickers[0])
        if sample_df.empty:
            needs_scrape = True

    if needs_scrape:
        logger.info("Scraping historical price data...")
        price_scraper = PriceScraper(config)
        price_scraper.scrape_and_store(session, tickers, start_date=args.start)

        fund_scraper = FundamentalScraper(config)
        fund_scraper.update_stock_master(session, tickers)
        logger.info("Scraping complete. Note: broker summary (real Asing FF) must be scraped separately via scrape_broker_summary workflow.")

    # Quality check
    good_tickers = []
    for ticker in tickers:
        qc = data_quality_check(session, ticker)
        if qc["status"] != "NO_DATA":
            good_tickers.append(ticker)

    if not good_tickers:
        logger.error("No valid tickers. Exiting.")
        sys.exit(1)

    logger.info(f"{len(good_tickers)} tickers with data")
    logger.info("Foreign flow source: real Asing net flow (aggregated from broker_summary into foreign_flow table)")

    # Load data
    start_dt = pd.Timestamp(args.start).date()
    end_dt = pd.Timestamp(args.end).date()

    # Load prices from 5 months before start for indicator warmup.
    # The 60-day breakout and MA50 need ~60+ trading days of history before
    # they produce valid values. Without this, the first ~3 months of a
    # backtest period are blind (e.g. BBTN's entire Mar-Apr 2025 rally was missed
    # because 60d high was NaN). Trading still only starts from start_dt.
    warmup_start = (pd.Timestamp(args.start) - pd.DateOffset(months=5)).date()

    universe_prices: Dict[str, pd.DataFrame] = {}
    foreign_flows: Dict[str, pd.DataFrame] = {}
    broker_accumulations: Dict[str, pd.DataFrame] = {}
    stock_sectors: Dict[str, str] = {}

    for ticker in good_tickers:
        pdf = load_prices_as_dataframe(session, ticker, warmup_start, end_dt)
        if not pdf.empty:
            universe_prices[ticker] = pdf
        # foreign_flow table now contains real aggregated Asing net flow
        # (pre-aggregated from broker_summary, replacing synthetic estimates)
        ff = load_foreign_flow_df(session, ticker, start_dt, end_dt)
        if not ff.empty:
            foreign_flows[ticker] = ff
        acc = load_broker_accumulation_df(session, ticker, start_dt, end_dt)
        if not acc.empty:
            broker_accumulations[ticker] = acc
        stock = session.query(Stock).filter_by(ticker=ticker).first()
        if stock and stock.sector:
            stock_sectors[ticker] = stock.sector

    ihsg_df = load_index_df(session, "IHSG", start_dt, end_dt)

    logger.info(f"Loaded {len(universe_prices)} stocks, IHSG: {len(ihsg_df)} days")

    if not universe_prices:
        logger.error("No price data. Exiting.")
        sys.exit(1)

    # Run backtest
    logger.info("Running backtest...")
    bt = BacktestEngine(config)
    equity_curve, trade_log, metrics = bt.run(
        universe_prices=universe_prices,
        ihsg_df=ihsg_df,
        foreign_flows=foreign_flows,
        broker_data=broker_accumulations,
        stock_sectors=stock_sectors,
    )

    # Reports
    benchmark_curve = None
    if not ihsg_df.empty:
        bench = ihsg_df["close"].reindex(equity_curve.index, method="ffill")
        if not bench.empty and bench.iloc[0] > 0:
            benchmark_curve = bench / bench.iloc[0] * args.capital

    generate_all_reports(equity_curve, trade_log, metrics,
                         benchmark_curve, args.output)

    print("\n" + format_metrics_report(metrics))
    print(f"\nReports saved to: {args.output}/")

    session.close()


if __name__ == "__main__":
    main()
