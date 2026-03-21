"""
Database schema for IDX Swing Trading Framework.
Uses SQLAlchemy ORM with SQLite (default) or PostgreSQL.
"""

import logging
from datetime import date, datetime
from typing import Optional

from sqlalchemy import (
    Column, Date, DateTime, Float, Index, Integer, String,
    Text, UniqueConstraint, create_engine, event,
)
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    pass


# ──────────────────────────────────────────────────────────────
# TABLES
# ──────────────────────────────────────────────────────────────

class Stock(Base):
    """Master list of IDX stocks."""
    __tablename__ = "stocks"

    ticker = Column(String(10), primary_key=True)         # e.g. "BBCA"
    name = Column(String(200))
    sector = Column(String(100))
    industry = Column(String(100))
    market_cap = Column(Float)                             # IDR
    shares_outstanding = Column(Float)
    free_float_pct = Column(Float)
    board = Column(String(50))                             # Main/Development/Acceleration
    last_updated = Column(DateTime, default=datetime.utcnow)


class DailyPrice(Base):
    """Daily OHLCV data (adjusted for splits/dividends)."""
    __tablename__ = "daily_prices"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ticker = Column(String(10), nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)
    open = Column(Float)
    high = Column(Float)
    low = Column(Float)
    close = Column(Float)
    volume = Column(Float)          # shares
    value = Column(Float)           # IDR traded value
    adj_close = Column(Float)       # split/dividend adjusted

    __table_args__ = (
        UniqueConstraint("ticker", "date", name="uq_price_ticker_date"),
        Index("ix_price_ticker_date", "ticker", "date"),
    )


class ForeignFlow(Base):
    """Daily net foreign buy/sell per stock."""
    __tablename__ = "foreign_flow"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ticker = Column(String(10), nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)
    foreign_buy_value = Column(Float, default=0)    # IDR
    foreign_sell_value = Column(Float, default=0)    # IDR
    foreign_buy_volume = Column(Float, default=0)    # shares
    foreign_sell_volume = Column(Float, default=0)   # shares
    net_foreign_value = Column(Float, default=0)     # buy - sell (IDR)
    net_foreign_volume = Column(Float, default=0)    # buy - sell (shares)

    __table_args__ = (
        UniqueConstraint("ticker", "date", name="uq_ff_ticker_date"),
    )


class BrokerSummary(Base):
    """Daily broker-level buy/sell per stock."""
    __tablename__ = "broker_summary"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ticker = Column(String(10), nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)
    broker_code = Column(String(10), nullable=False, index=True)
    broker_type = Column(String(20), default="")  # "Asing", "Lokal", "Pemerintah"
    buy_value = Column(Float, default=0)
    sell_value = Column(Float, default=0)
    buy_volume = Column(Float, default=0)
    sell_volume = Column(Float, default=0)
    net_value = Column(Float, default=0)
    net_volume = Column(Float, default=0)

    __table_args__ = (
        UniqueConstraint("ticker", "date", "broker_code", name="uq_bs_ticker_date_broker"),
    )


class CorporateAction(Base):
    """Stock splits, dividends, rights issues."""
    __tablename__ = "corporate_actions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ticker = Column(String(10), nullable=False, index=True)
    date = Column(Date, nullable=False)
    action_type = Column(String(50))   # SPLIT, DIVIDEND, RIGHTS, BONUS
    description = Column(Text)
    ratio_or_amount = Column(Float)    # split ratio or dividend per share
    cum_date = Column(Date)
    ex_date = Column(Date)


class IndexDaily(Base):
    """IHSG (^JKSE) daily data for regime calculation."""
    __tablename__ = "index_daily"

    id = Column(Integer, primary_key=True, autoincrement=True)
    index_code = Column(String(20), nullable=False, default="IHSG")
    date = Column(Date, nullable=False, index=True)
    open = Column(Float)
    high = Column(Float)
    low = Column(Float)
    close = Column(Float)
    volume = Column(Float)

    __table_args__ = (
        UniqueConstraint("index_code", "date", name="uq_index_date"),
    )


class SignalLog(Base):
    """Persisted signal scores for audit trail."""
    __tablename__ = "signal_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ticker = Column(String(10), nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)
    market_regime = Column(String(20))
    foreign_flow_score = Column(Float)
    volume_price_score = Column(Float)
    broker_score = Column(Float)
    composite_score = Column(Float)
    technical_pass = Column(Integer)   # 0 or 1
    signal = Column(String(10))        # BUY, SELL, HOLD


# ──────────────────────────────────────────────────────────────
# ENGINE & SESSION
# ──────────────────────────────────────────────────────────────

def get_engine(db_url: str):
    """Create SQLAlchemy engine with appropriate settings."""
    engine = create_engine(
        db_url,
        echo=False,
        pool_pre_ping=True,
    )
    # Enable WAL mode for SQLite (better concurrent reads)
    if "sqlite" in db_url:
        @event.listens_for(engine, "connect")
        def set_sqlite_pragma(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.close()
    return engine


def create_all_tables(db_url: str):
    """Create all tables if they don't exist."""
    engine = get_engine(db_url)
    Base.metadata.create_all(engine)
    logger.info("All database tables created / verified.")
    return engine


def get_session(engine) -> Session:
    """Return a new session bound to the engine."""
    SessionLocal = sessionmaker(bind=engine)
    return SessionLocal()
