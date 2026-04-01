"""
Bulk data loading utilities.
Handles upsert logic (insert or update on conflict) and data quality checks.
"""

import logging
from datetime import date
from typing import Dict, List, Optional

import pandas as pd
from sqlalchemy import text
from sqlalchemy.orm import Session

from database.schema import (
    BrokerSummary, CorporateAction, DailyPrice, ForeignFlow,
    IndexDaily, Stock, get_engine, get_session,
)

logger = logging.getLogger(__name__)


def upsert_daily_prices(session: Session, df: pd.DataFrame, ticker: str):
    """
    Insert or update daily price rows.
    df must have columns: date, open, high, low, close, volume, value, adj_close
    """
    if df.empty:
        return 0

    count = 0
    for _, row in df.iterrows():
        existing = (
            session.query(DailyPrice)
            .filter_by(ticker=ticker, date=row["date"])
            .first()
        )
        if existing:
            # Update if data changed
            for col in ["open", "high", "low", "close", "volume", "value", "adj_close"]:
                if col in row and pd.notna(row[col]):
                    setattr(existing, col, float(row[col]))
        else:
            dp = DailyPrice(
                ticker=ticker,
                date=row["date"],
                open=_safe_float(row.get("open")),
                high=_safe_float(row.get("high")),
                low=_safe_float(row.get("low")),
                close=_safe_float(row.get("close")),
                volume=_safe_float(row.get("volume")),
                value=_safe_float(row.get("value")),
                adj_close=_safe_float(row.get("adj_close")),
            )
            session.add(dp)
            count += 1

    session.commit()
    logger.info(f"Upserted {count} new price rows for {ticker}")
    return count


def upsert_foreign_flow(session: Session, df: pd.DataFrame, ticker: str):
    """Insert or update foreign flow rows."""
    if df.empty:
        return 0

    count = 0
    for _, row in df.iterrows():
        existing = (
            session.query(ForeignFlow)
            .filter_by(ticker=ticker, date=row["date"])
            .first()
        )
        if existing:
            for col in ["foreign_buy_value", "foreign_sell_value",
                        "foreign_buy_volume", "foreign_sell_volume",
                        "net_foreign_value", "net_foreign_volume"]:
                if col in row and pd.notna(row[col]):
                    setattr(existing, col, float(row[col]))
        else:
            ff = ForeignFlow(
                ticker=ticker,
                date=row["date"],
                foreign_buy_value=_safe_float(row.get("foreign_buy_value")),
                foreign_sell_value=_safe_float(row.get("foreign_sell_value")),
                foreign_buy_volume=_safe_float(row.get("foreign_buy_volume")),
                foreign_sell_volume=_safe_float(row.get("foreign_sell_volume")),
                net_foreign_value=_safe_float(row.get("net_foreign_value")),
                net_foreign_volume=_safe_float(row.get("net_foreign_volume")),
            )
            session.add(ff)
            count += 1

    session.commit()
    logger.info(f"Upserted {count} foreign flow rows for {ticker}")
    return count


def upsert_index_daily(session: Session, df: pd.DataFrame, index_code: str = "IHSG"):
    """Insert or update index daily rows."""
    if df.empty:
        return 0

    count = 0
    for _, row in df.iterrows():
        existing = (
            session.query(IndexDaily)
            .filter_by(index_code=index_code, date=row["date"])
            .first()
        )
        if existing:
            for col in ["open", "high", "low", "close", "volume"]:
                if col in row and pd.notna(row[col]):
                    setattr(existing, col, float(row[col]))
        else:
            idx = IndexDaily(
                index_code=index_code,
                date=row["date"],
                open=_safe_float(row.get("open")),
                high=_safe_float(row.get("high")),
                low=_safe_float(row.get("low")),
                close=_safe_float(row.get("close")),
                volume=_safe_float(row.get("volume")),
            )
            session.add(idx)
            count += 1

    session.commit()
    logger.info(f"Upserted {count} index rows for {index_code}")
    return count


def load_prices_as_dataframe(session: Session, ticker: str,
                              start_date: Optional[date] = None,
                              end_date: Optional[date] = None) -> pd.DataFrame:
    """Load daily price data into a pandas DataFrame."""
    q = session.query(DailyPrice).filter(DailyPrice.ticker == ticker)
    if start_date:
        q = q.filter(DailyPrice.date >= start_date)
    if end_date:
        q = q.filter(DailyPrice.date <= end_date)
    q = q.order_by(DailyPrice.date)

    rows = q.all()
    if not rows:
        return pd.DataFrame()

    data = [{
        "date": r.date, "open": r.open, "high": r.high,
        "low": r.low, "close": r.close, "volume": r.volume,
        "value": r.value, "adj_close": r.adj_close,
    } for r in rows]

    df = pd.DataFrame(data)
    df["date"] = pd.to_datetime(df["date"])
    df.set_index("date", inplace=True)
    return df


def load_foreign_flow_df(session: Session, ticker: str,
                          start_date: Optional[date] = None,
                          end_date: Optional[date] = None) -> pd.DataFrame:
    """Load foreign flow data as DataFrame."""
    q = session.query(ForeignFlow).filter(ForeignFlow.ticker == ticker)
    if start_date:
        q = q.filter(ForeignFlow.date >= start_date)
    if end_date:
        q = q.filter(ForeignFlow.date <= end_date)
    q = q.order_by(ForeignFlow.date)

    rows = q.all()
    if not rows:
        return pd.DataFrame()

    data = [{
        "date": r.date,
        "net_foreign_value": r.net_foreign_value,
        "net_foreign_volume": r.net_foreign_volume,
        "foreign_buy_value": r.foreign_buy_value,
        "foreign_sell_value": r.foreign_sell_value,
    } for r in rows]

    df = pd.DataFrame(data)
    df["date"] = pd.to_datetime(df["date"])
    df.set_index("date", inplace=True)
    return df


def load_broker_summary_as_ff_df(session: Session, ticker: str,
                                  start_date: Optional[date] = None,
                                  end_date: Optional[date] = None) -> pd.DataFrame:
    """
    Load real Asing (foreign) net flow from broker_summary table,
    aggregated per day across all foreign broker codes.

    Returns a DataFrame with a net_foreign_value column — same interface
    as load_foreign_flow_df(), so it is a drop-in replacement for the
    foreign_flows dict used in SignalCombiner._add_foreign_flow_signals().
    """
    q = (
        session.query(BrokerSummary)
        .filter(
            BrokerSummary.ticker == ticker,
            BrokerSummary.broker_type == "Asing",
        )
    )
    if start_date:
        q = q.filter(BrokerSummary.date >= start_date)
    if end_date:
        q = q.filter(BrokerSummary.date <= end_date)
    q = q.order_by(BrokerSummary.date)

    rows = q.all()
    if not rows:
        return pd.DataFrame()

    data = [{"date": r.date, "net_value": r.net_value or 0.0} for r in rows]
    df = pd.DataFrame(data)
    df["date"] = pd.to_datetime(df["date"])

    # Sum all Asing broker codes per day → single net_foreign_value per date
    df = (
        df.groupby("date")["net_value"]
        .sum()
        .rename("net_foreign_value")
        .to_frame()
    )
    return df


def load_index_df(session: Session, index_code: str = "IHSG",
                   start_date: Optional[date] = None,
                   end_date: Optional[date] = None) -> pd.DataFrame:
    """Load index daily data as DataFrame."""
    q = session.query(IndexDaily).filter(IndexDaily.index_code == index_code)
    if start_date:
        q = q.filter(IndexDaily.date >= start_date)
    if end_date:
        q = q.filter(IndexDaily.date <= end_date)
    q = q.order_by(IndexDaily.date)

    rows = q.all()
    if not rows:
        return pd.DataFrame()

    data = [{
        "date": r.date, "open": r.open, "high": r.high,
        "low": r.low, "close": r.close, "volume": r.volume,
    } for r in rows]

    df = pd.DataFrame(data)
    df["date"] = pd.to_datetime(df["date"])
    df.set_index("date", inplace=True)
    return df


def data_quality_check(session: Session, ticker: str) -> Dict:
    """Run basic data quality checks on a ticker's price data."""
    df = load_prices_as_dataframe(session, ticker)
    if df.empty:
        return {"ticker": ticker, "status": "NO_DATA"}

    issues = []

    # Check for gaps (missing trading days)
    date_diffs = df.index.to_series().diff().dt.days
    big_gaps = date_diffs[date_diffs > 5]  # more than 5 calendar days
    if len(big_gaps) > 0:
        issues.append(f"{len(big_gaps)} suspicious gaps in data")

    # Check for zero or negative prices
    for col in ["open", "high", "low", "close"]:
        zeros = (df[col] <= 0).sum()
        if zeros > 0:
            issues.append(f"{zeros} rows with {col} <= 0")

    # Check OHLC consistency
    bad_hl = (df["high"] < df["low"]).sum()
    if bad_hl > 0:
        issues.append(f"{bad_hl} rows where high < low")

    # Check for duplicates
    dup_count = df.index.duplicated().sum()
    if dup_count > 0:
        issues.append(f"{dup_count} duplicate dates")

    return {
        "ticker": ticker,
        "status": "OK" if not issues else "ISSUES",
        "rows": len(df),
        "date_range": f"{df.index.min()} to {df.index.max()}",
        "issues": issues,
    }


def _safe_float(val) -> Optional[float]:
    """Convert value to float, returning None for NaN/None."""
    if val is None:
        return None
    try:
        f = float(val)
        if pd.isna(f):
            return None
        return f
    except (ValueError, TypeError):
        return None
