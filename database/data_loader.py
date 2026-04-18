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
    Load Asing (foreign institutional) net flow from broker_summary.

    Returns daily aggregated Asing net_value as net_foreign_value — same
    interface as load_foreign_flow_df().

    Note: signal_combiner.py's is_foreign_driven check (Asing ratio > 5% of
    daily traded value) determines whether the FF filter applies. If a ticker
    is not foreign-driven, the FF filter is skipped automatically regardless
    of the values returned here.
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

    data = [{"date": r.date, "net_foreign_value": r.net_value or 0.0}
            for r in rows]
    df = pd.DataFrame(data)
    df["date"] = pd.to_datetime(df["date"])
    result = df.groupby("date")["net_foreign_value"].sum().to_frame()
    return result


def load_broker_accumulation_df(session: Session, ticker: str,
                                  start_date: Optional[date] = None,
                                  end_date: Optional[date] = None) -> pd.DataFrame:
    """
    Compute per-broker accumulation/distribution score for a ticker.

    For each date D, looks at each Asing broker's activity over the prior 5 days:
      - Accumulating: traded on 3+ days AND was net buyer on 4+ of those days
      - Distributing: traded on 3+ days AND was net buyer on <=1 of those days

    Returns DataFrame indexed by date with 'accumulation_score' column:
      score = count(accumulating brokers) - count(distributing brokers)
      Positive = more brokers accumulating than distributing.
      Negative = more brokers distributing (potential exit signal).
      Zero     = neutral / no persistent directional activity.
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

    data = [{"date": r.date, "broker_code": r.broker_code, "net_value": r.net_value or 0.0}
            for r in rows]
    df = pd.DataFrame(data)
    df["date"] = pd.to_datetime(df["date"])

    # Pivot: rows=date, columns=broker_code, values=net_value (NaN = did not trade)
    pivot = df.pivot_table(index="date", columns="broker_code",
                           values="net_value", aggfunc="sum")

    # Per broker: 1 if net buyer that day, 0 if net seller, NaN if no trade
    is_buy = (pivot > 0).astype(float).where(pivot.notna())
    is_active = pivot.notna().astype(float)

    # Rolling 5-day sums per broker
    buy_days = is_buy.rolling(5, min_periods=1).sum()
    active_days = is_active.rolling(5, min_periods=1).sum()

    # Accumulating: active 3+ days AND net buyer 4+ days
    accumulating = ((active_days >= 3) & (buy_days >= 4))
    # Distributing: active 3+ days AND net buyer <=1 day (net seller 4+ days)
    distributing = ((active_days >= 3) & (buy_days <= 1))

    score = accumulating.sum(axis=1) - distributing.sum(axis=1)

    # ── Top-N broker accumulation (value-weighted) ──
    # For following big money: look at the top 5 Asing brokers by activity
    # over a 10-day rolling window. Sum their net_value — if positive,
    # the big players are net buying (accumulating), not the noise of
    # many small brokers.
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

    result = pd.DataFrame({
        "accumulation_score": score,
        "top_broker_acc": top_scores,
    }, index=score.index)
    return result


def load_fp_ratios(session: Session,
                   start_date: Optional[date] = None,
                   end_date: Optional[date] = None) -> Dict[str, float]:
    """
    Compute foreign participation ratio per ticker from broker_summary.

    fp_ratio = Asing traded value (buy+sell) / total traded value (all brokers).
    Range 0.0–1.0. High value = foreigners dominate trading; low = domestics dominate.

    Used as an entry filter: high-fp stocks show lower win rates because foreigners
    use them as liquid hedges (sell during drawdowns, buy during rallies), creating
    false breakouts driven by domestic retail momentum, not fundamental buying.
    """
    filters = []
    params: Dict = {}
    if start_date:
        filters.append("date >= :start_date")
        params["start_date"] = str(start_date)
    if end_date:
        filters.append("date <= :end_date")
        params["end_date"] = str(end_date)

    where = ("WHERE " + " AND ".join(filters)) if filters else ""
    sql = text(f"""
        SELECT ticker,
            CAST(
                SUM(CASE WHEN broker_type = 'Asing' THEN buy_value + sell_value ELSE 0 END)
                AS REAL
            ) /
            NULLIF(SUM(buy_value + sell_value), 0) AS fp_ratio
        FROM broker_summary
        {where}
        GROUP BY ticker
    """)
    rows = session.execute(sql, params).fetchall()
    return {r[0]: float(r[1]) for r in rows if r[1] is not None}


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
