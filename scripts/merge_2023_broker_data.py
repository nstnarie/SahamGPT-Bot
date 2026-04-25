"""
Step 1 of 2023 integration: Merge 2023 broker_summary from artifact into local DB.

Usage:
    python3 scripts/merge_2023_broker_data.py --artifact /tmp/artifact_db/idx_swing_trader.db

The GitHub artifact DB contains accumulated broker_summary including 2023.
This script copies all pre-2024 rows into the local idx_swing_trader.db.
Uses INSERT OR IGNORE so re-runs are safe.
"""

import argparse
import sqlite3
from pathlib import Path


def merge(artifact_path: str, local_path: str = "idx_swing_trader.db"):
    artifact = Path(artifact_path)
    local = Path(local_path)

    if not artifact.exists():
        print(f"ERROR: Artifact DB not found at {artifact}")
        return False

    print(f"Artifact DB: {artifact} ({artifact.stat().st_size / 1e6:.1f} MB)")
    print(f"Local DB:    {local} ({local.stat().st_size / 1e6:.1f} MB)")

    art_conn = sqlite3.connect(str(artifact))

    # Verify artifact has 2023 data
    rows = art_conn.execute(
        "SELECT MIN(date), MAX(date), COUNT(*) FROM broker_summary WHERE date < '2024-01-01'"
    ).fetchone()
    print(f"\nArtifact 2023 broker_summary: {rows[0]} to {rows[1]}, {rows[2]:,} rows")

    if not rows[2]:
        print("No 2023 data found in artifact. Aborting.")
        art_conn.close()
        return False

    art_conn.close()

    # Merge via ATTACH
    loc_conn = sqlite3.connect(str(local))

    existing = loc_conn.execute(
        "SELECT COUNT(*) FROM broker_summary WHERE date < '2024-01-01'"
    ).fetchone()[0]
    print(f"Local 2023 broker_summary before merge: {existing:,} rows")

    loc_conn.execute(f"ATTACH DATABASE '{artifact}' AS artifact")
    loc_conn.execute("BEGIN")
    loc_conn.execute("""
        INSERT OR IGNORE INTO main.broker_summary
            (date, ticker, broker_code, broker_type,
             buy_value, sell_value, buy_volume, sell_volume, net_value, net_volume)
        SELECT
            date, ticker, broker_code, broker_type,
            buy_value, sell_value, buy_volume, sell_volume, net_value, net_volume
        FROM artifact.broker_summary
        WHERE date < '2024-01-01'
    """)
    inserted = loc_conn.execute("SELECT changes()").fetchone()[0]
    loc_conn.execute("COMMIT")

    final = loc_conn.execute(
        "SELECT MIN(date), MAX(date), COUNT(*) FROM broker_summary WHERE date < '2024-01-01'"
    ).fetchone()
    total = loc_conn.execute("SELECT COUNT(*) FROM broker_summary").fetchone()[0]

    print(f"\nInserted {inserted:,} new rows")
    print(f"Local 2023 broker_summary after merge: {final[0]} to {final[1]}, {final[2]:,} rows")
    print(f"Total broker_summary rows: {total:,}")

    # Quick sanity check — count by quarter
    print("\nRow count by quarter:")
    for q_start, q_end, label in [
        ("2023-01-01", "2023-03-31", "2023-Q1"),
        ("2023-04-01", "2023-06-30", "2023-Q2"),
        ("2023-07-01", "2023-09-30", "2023-Q3"),
        ("2023-10-01", "2023-12-31", "2023-Q4"),
    ]:
        n = loc_conn.execute(
            f"SELECT COUNT(*) FROM broker_summary WHERE date >= '{q_start}' AND date <= '{q_end}'"
        ).fetchone()[0]
        tickers = loc_conn.execute(
            f"SELECT COUNT(DISTINCT ticker) FROM broker_summary WHERE date >= '{q_start}' AND date <= '{q_end}'"
        ).fetchone()[0]
        print(f"  {label}: {n:,} rows, {tickers} tickers")

    loc_conn.close()
    print("\nStep 1 complete. Run step 2: aggregate_2023_foreign_flow.py")
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact", required=True, help="Path to downloaded artifact DB")
    parser.add_argument("--local", default="idx_swing_trader.db", help="Local DB path")
    args = parser.parse_args()
    merge(args.artifact, args.local)
