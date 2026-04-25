"""
Step 2 of 2023 integration: Re-aggregate 2023 broker_summary → foreign_flow table.

Must run AFTER merge_2023_broker_data.py.

The existing 2023 foreign_flow rows are partial/KSEI-based (only ~36% have buy data).
This script replaces them with real Asing broker data aggregated from broker_summary,
matching the same pattern used for 2024-2025.

Usage:
    python3 scripts/aggregate_2023_foreign_flow.py
"""

import sys
from datetime import date

import pandas as pd

sys.path.insert(0, ".")
from database.schema import get_engine, get_session
from database.data_loader import upsert_foreign_flow
from sqlalchemy import text


TICKERS_SQL = "SELECT DISTINCT ticker FROM broker_summary WHERE date < '2024-01-01' ORDER BY ticker"
AGG_SQL = """
    SELECT
        date,
        SUM(CASE WHEN broker_type = 'Asing' THEN buy_value ELSE 0 END)  AS foreign_buy_value,
        SUM(CASE WHEN broker_type = 'Asing' THEN sell_value ELSE 0 END) AS foreign_sell_value,
        SUM(CASE WHEN broker_type = 'Asing' THEN buy_volume ELSE 0 END) AS foreign_buy_volume,
        SUM(CASE WHEN broker_type = 'Asing' THEN sell_volume ELSE 0 END) AS foreign_sell_volume
    FROM broker_summary
    WHERE ticker = :ticker AND date < '2024-01-01'
    GROUP BY date
    ORDER BY date
"""


def aggregate(local_path: str = "idx_swing_trader.db"):
    engine = get_engine(f"sqlite:///{local_path}")
    session = get_session(engine)

    # Verify 2023 broker_summary is present
    count = session.execute(
        text("SELECT COUNT(*) FROM broker_summary WHERE date < '2024-01-01'")
    ).scalar()
    if count == 0:
        print("ERROR: No 2023 broker_summary data. Run merge_2023_broker_data.py first.")
        session.close()
        return

    print(f"Found {count:,} 2023 broker_summary rows. Aggregating into foreign_flow...")

    tickers = [r[0] for r in session.execute(text(TICKERS_SQL)).fetchall()]
    print(f"Tickers with 2023 data: {len(tickers)}")

    total_upserted = 0
    for i, ticker in enumerate(tickers, 1):
        rows = session.execute(text(AGG_SQL), {"ticker": ticker}).fetchall()
        if not rows:
            continue

        df = pd.DataFrame(rows, columns=[
            "date", "foreign_buy_value", "foreign_sell_value",
            "foreign_buy_volume", "foreign_sell_volume"
        ])
        df["date"] = pd.to_datetime(df["date"])
        df["net_foreign_value"] = df["foreign_buy_value"] - df["foreign_sell_value"]
        df["net_foreign_volume"] = df["foreign_buy_volume"] - df["foreign_sell_volume"]

        n = upsert_foreign_flow(session, df, ticker)
        total_upserted += n

        if i % 20 == 0 or i == len(tickers):
            print(f"  [{i}/{len(tickers)}] {ticker}: {len(df)} days")

    session.close()
    print(f"\nTotal foreign_flow rows upserted: {total_upserted:,}")

    # Verify
    import sqlite3
    conn = sqlite3.connect(local_path)
    r = conn.execute(
        "SELECT COUNT(*), SUM(CASE WHEN foreign_buy_value > 0 THEN 1 ELSE 0 END) "
        "FROM foreign_flow WHERE date >= '2023-01-01' AND date < '2024-01-01'"
    ).fetchone()
    print(f"\n2023 foreign_flow after aggregation: {r[0]:,} rows, {r[1]:,} with buy data")
    conn.close()
    print("\nStep 2 complete. Ready to run 2023 backtest.")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--local", default="idx_swing_trader.db")
    args = parser.parse_args()
    aggregate(args.local)
