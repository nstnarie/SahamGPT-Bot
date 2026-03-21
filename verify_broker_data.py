"""
Verify Broker Summary Data
=============================
Run this after scraping to check if data looks correct.
Compares against known facts (e.g., BBCA should have heavy foreign activity).

Usage:
  python3 verify_broker_data.py
  
Or run via GitHub Actions workflow.
"""

import os
import sys
import logging
from datetime import date, datetime, timedelta

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
logger = logging.getLogger(__name__)


def verify():
    from database.schema import get_session, BrokerSummary, create_all_tables
    
    create_all_tables()
    session = get_session()

    # 1. Basic counts
    total_records = session.query(BrokerSummary).count()
    print(f"\n{'='*60}")
    print(f"  BROKER SUMMARY DATA VERIFICATION")
    print(f"{'='*60}")
    print(f"\n  Total records in database: {total_records}")

    if total_records == 0:
        print("\n  ❌ NO DATA FOUND. The scraper didn't store anything.")
        print("  Check:")
        print("    - Are STOCKBIT_USERNAME and STOCKBIT_PASSWORD set?")
        print("    - Did the login succeed? (check workflow logs)")
        print("    - Is the API endpoint responding?")
        session.close()
        return False

    # 2. Date range
    from sqlalchemy import func
    min_date = session.query(func.min(BrokerSummary.date)).scalar()
    max_date = session.query(func.max(BrokerSummary.date)).scalar()
    unique_dates = session.query(func.count(func.distinct(BrokerSummary.date))).scalar()
    unique_tickers = session.query(func.count(func.distinct(BrokerSummary.ticker))).scalar()
    unique_brokers = session.query(func.count(func.distinct(BrokerSummary.broker_code))).scalar()

    print(f"\n  Date range: {min_date} to {max_date}")
    print(f"  Unique trading days: {unique_dates}")
    print(f"  Unique tickers: {unique_tickers}")
    print(f"  Unique broker codes: {unique_brokers}")
    print(f"  Avg records per ticker per day: {total_records / max(unique_dates * unique_tickers, 1):.1f}")

    # 3. Broker type distribution
    print(f"\n  BROKER TYPE DISTRIBUTION:")
    from sqlalchemy import case
    types = (
        session.query(
            BrokerSummary.broker_type,
            func.count(BrokerSummary.id),
            func.sum(BrokerSummary.net_value),
        )
        .group_by(BrokerSummary.broker_type)
        .all()
    )
    for btype, count, net_val in types:
        label = btype if btype else "(empty)"
        print(f"    {label:<15} {count:>6} records | Net value: Rp {(net_val or 0):>15,.0f}")

    has_types = any(t[0] for t in types)
    if not has_types:
        print("\n  ⚠️  WARNING: broker_type is empty for all records.")
        print("  This means the type field wasn't parsed from the API response.")
        print("  Foreign flow classification will fall back to manual broker code list.")

    # 4. Sample data for a known stock (BBCA if available)
    test_tickers = ["BBCA", "BBRI", "TLKM", "ASII"]
    for test_ticker in test_tickers:
        records = (
            session.query(BrokerSummary)
            .filter_by(ticker=test_ticker)
            .order_by(BrokerSummary.date.desc())
            .limit(50)
            .all()
        )
        if not records:
            continue

        print(f"\n  SAMPLE: {test_ticker} (latest date: {records[0].date})")

        # Group by date
        dates_seen = {}
        for r in records:
            if r.date not in dates_seen:
                dates_seen[r.date] = {"foreign": 0, "local": 0, "govt": 0, "count": 0}
            dates_seen[r.date]["count"] += 1
            btype = (r.broker_type or "").strip()
            if btype == "Asing":
                dates_seen[r.date]["foreign"] += r.net_value
            elif btype == "Pemerintah":
                dates_seen[r.date]["govt"] += r.net_value
            else:
                dates_seen[r.date]["local"] += r.net_value

        for d in sorted(dates_seen.keys(), reverse=True)[:5]:
            info = dates_seen[d]
            foreign_dir = "BUY" if info["foreign"] > 0 else "SELL"
            print(f"    {d} | {info['count']:>2} brokers | "
                  f"Foreign: Rp {info['foreign']:>14,.0f} ({foreign_dir}) | "
                  f"Local: Rp {info['local']:>14,.0f}")

        # Sanity check: BBCA should have significant foreign activity
        if test_ticker == "BBCA":
            latest = list(dates_seen.values())[0] if dates_seen else {}
            if latest.get("count", 0) < 5:
                print(f"  ⚠️  BBCA has only {latest.get('count', 0)} brokers. Expected 20-50.")
                print(f"     This might indicate the API returned limited data.")
            else:
                print(f"  ✅  BBCA broker count looks normal ({latest['count']} brokers)")

            if abs(latest.get("foreign", 0)) < 1_000_000_000:
                print(f"  ⚠️  BBCA foreign flow seems low (Rp {latest.get('foreign', 0):,.0f}).")
                print(f"     Expected billions. Check if 'Asing' type is being parsed.")
            else:
                print(f"  ✅  BBCA foreign flow magnitude looks correct")

        break  # Only show first available ticker in detail

    # 5. Top foreign net buyers/sellers across all data
    print(f"\n  TOP NET FOREIGN BUYER STOCKS (most recent date):")
    if max_date:
        ticker_foreign = (
            session.query(
                BrokerSummary.ticker,
                func.sum(BrokerSummary.net_value),
            )
            .filter(
                BrokerSummary.date == max_date,
                BrokerSummary.broker_type == "Asing",
            )
            .group_by(BrokerSummary.ticker)
            .order_by(func.sum(BrokerSummary.net_value).desc())
            .limit(5)
            .all()
        )
        for ticker, net_val in ticker_foreign:
            direction = "NET BUY" if net_val > 0 else "NET SELL"
            print(f"    {ticker:<6} Rp {net_val:>15,.0f} ({direction})")

        if not ticker_foreign:
            print("    (no Asing-type records found — check broker_type parsing)")

    # 6. Summary verdict
    print(f"\n{'='*60}")
    issues = []
    if total_records < 100:
        issues.append("Very few records — scraping may have partially failed")
    if not has_types:
        issues.append("broker_type is empty — foreign flow won't work from type field")
    if unique_brokers < 10:
        issues.append(f"Only {unique_brokers} unique broker codes — expected 30-80")

    if not issues:
        print(f"  ✅  DATA LOOKS GOOD!")
        print(f"     {total_records} records, {unique_dates} days, {unique_tickers} tickers")
        print(f"     Broker types are populated. Ready for backtesting.")
    else:
        print(f"  ⚠️  ISSUES FOUND:")
        for issue in issues:
            print(f"     - {issue}")

    print(f"{'='*60}\n")

    session.close()
    return len(issues) == 0


if __name__ == "__main__":
    success = verify()
    sys.exit(0 if success else 1)
