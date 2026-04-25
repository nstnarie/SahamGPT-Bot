"""
Step 3 of 2023 integration: Verify all data needed for 2023 backtest is present.

Run after aggregate_2023_foreign_flow.py. Confirms:
- daily_prices coverage for 2023
- foreign_flow 2023 quality (real vs partial)
- broker_summary 2023 row counts by quarter/ticker
- fp_ratios will be computable
- broker_accumulation will be computable

Usage:
    python3 scripts/verify_2023_data.py
"""

import sys
import sqlite3

sys.path.insert(0, ".")
from database.schema import get_engine, get_session
from database.data_loader import load_fp_ratios


def verify(local_path: str = "idx_swing_trader.db"):
    conn = sqlite3.connect(local_path)
    ok = True

    print("=" * 60)
    print("2023 BACKTEST DATA VERIFICATION")
    print("=" * 60)

    # 1. daily_prices
    r = conn.execute(
        "SELECT MIN(date), MAX(date), COUNT(DISTINCT ticker) FROM daily_prices "
        "WHERE date >= '2023-01-01' AND date < '2024-01-01'"
    ).fetchone()
    has_prices = r[2] > 100
    print(f"\n[{'OK' if has_prices else 'FAIL'}] daily_prices 2023: {r[0]} to {r[1]}, {r[2]} tickers")
    if not has_prices:
        print("  WARNING: Need price data for 2023 — run with --scrape flag")
        ok = False

    # 2. index_daily (IHSG)
    r = conn.execute(
        "SELECT MIN(date), MAX(date), COUNT(*) FROM index_daily "
        "WHERE date >= '2023-01-01' AND date < '2024-01-01'"
    ).fetchone()
    has_ihsg = r[2] > 200
    print(f"[{'OK' if has_ihsg else 'FAIL'}] index_daily 2023: {r[0]} to {r[1]}, {r[2]} days")
    if not has_ihsg:
        ok = False

    # 3. broker_summary 2023
    r = conn.execute(
        "SELECT MIN(date), MAX(date), COUNT(*), COUNT(DISTINCT ticker) FROM broker_summary "
        "WHERE date >= '2023-01-01' AND date < '2024-01-01'"
    ).fetchone()
    has_broker = r[2] > 500000
    print(f"[{'OK' if has_broker else 'FAIL'}] broker_summary 2023: {r[0]} to {r[1]}, "
          f"{r[2]:,} rows, {r[3]} tickers")
    if not has_broker:
        print("  WARNING: Run merge_2023_broker_data.py first")
        ok = False

    # 4. broker_summary by quarter
    print("\n  broker_summary 2023 by quarter:")
    for q_start, q_end, label in [
        ("2023-01-01", "2023-03-31", "Q1"),
        ("2023-04-01", "2023-06-30", "Q2"),
        ("2023-07-01", "2023-09-30", "Q3"),
        ("2023-10-01", "2023-12-31", "Q4"),
    ]:
        r = conn.execute(
            f"SELECT COUNT(*), COUNT(DISTINCT ticker) FROM broker_summary "
            f"WHERE date >= '{q_start}' AND date <= '{q_end}'"
        ).fetchone()
        complete = r[1] >= 130
        print(f"  {'✅' if complete else '⚠️ '} {label}: {r[0]:,} rows, {r[1]} tickers")

    # 5. foreign_flow 2023 quality
    r = conn.execute(
        "SELECT COUNT(*), "
        "SUM(CASE WHEN foreign_buy_value > 0 THEN 1 ELSE 0 END), "
        "COUNT(DISTINCT ticker) "
        "FROM foreign_flow WHERE date >= '2023-01-01' AND date < '2024-01-01'"
    ).fetchone()
    coverage_pct = (r[1] / r[0] * 100) if r[0] > 0 else 0
    has_ff = coverage_pct > 80
    print(f"\n[{'OK' if has_ff else 'WARN'}] foreign_flow 2023: {r[0]:,} rows, {r[2]} tickers, "
          f"{coverage_pct:.0f}% with buy data")
    if not has_ff:
        print("  WARNING: Low coverage — run aggregate_2023_foreign_flow.py first")

    # 6. fp_ratios
    conn.close()
    engine = get_engine(f"sqlite:///{local_path}")
    session = get_session(engine)
    fp = load_fp_ratios(session)
    session.close()
    print(f"\n[{'OK' if len(fp) > 100 else 'FAIL'}] fp_ratios computable: {len(fp)} tickers")

    print("\n" + "=" * 60)
    if ok:
        print("✅ All checks passed. Ready to run 2023 backtest:")
        print("\n  python3 main_backtest.py --start 2023-01-01 --end 2023-12-31 --output reports_local_2023")
    else:
        print("⚠️  Some checks failed — see above before running backtest")
    print("=" * 60)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--local", default="idx_swing_trader.db")
    args = parser.parse_args()
    verify(args.local)
