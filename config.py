"""
IDX Swing Trading Framework — Configuration v4
=================================================
REBUILT: Breakout detection + real foreign flow confirmation.
Based on SahamGPT proven rules from 16 backtest iterations.

DISCLAIMER: For educational and research purposes only.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional
import os

TIMEZONE = "Asia/Jakarta"
CURRENCY = "IDR"
DATABASE_URL = os.getenv("IDX_DB_URL", "sqlite:///idx_swing_trader.db")
LOT_SIZE = 100

TRADING_HOURS = {
    "pre_open":  ("08:45", "09:00"),
    "session_1": ("09:00", "12:00"),
    "session_2": ("13:30", "16:15"),
}

BUY_COMMISSION = 0.0015
SELL_COMMISSION = 0.0025
SLIPPAGE_TICKS = 1

TICK_SIZE_TABLE = [
    (1, 50, 1), (51, 200, 2), (201, 500, 5),
    (501, 2_000, 10), (2_001, 5_000, 25), (5_001, float("inf"), 50),
]

ARA_ARB_LIMITS = {"acceleration_board": 0.35, "regular": 0.25, "development_board": 0.35}


@dataclass
class UniverseConfig:
    index_membership: str = "LQ45"
    min_avg_daily_value: float = 5_000_000_000
    min_market_cap: float = 1_000_000_000_000
    max_spread_pct: Optional[float] = 0.02
    excluded_sectors: List[str] = field(default_factory=list)


@dataclass
class MarketRegimeConfig:
    ema_fast: int = 20
    ema_medium: int = 50
    ema_slow: int = 200
    breadth_period: int = 50
    breadth_bull_threshold: float = 0.60
    breadth_bear_threshold: float = 0.40
    exposure_multiplier: Dict[str, float] = field(default_factory=lambda: {
        "BULL": 1.0, "SIDEWAYS": 0.5, "BEAR": 0.0,
    })


# ──────────────────────────────────────────────────────────────
# BREAKOUT DETECTION (PRIMARY SIGNAL)
# ──────────────────────────────────────────────────────────────

@dataclass
class BreakoutConfig:
    """
    Primary entry signal: price breaks above consolidation range
    with volume confirmation. This is observable fact, not estimation.
    """
    # Close must exceed the N-day highest high
    breakout_period: int = 20

    # Volume spike on breakout day
    volume_spike_min: float = 1.5   # minimum 1.5x average
    volume_spike_max: float = 5.0   # cap at 5x (filter pump-and-dumps)

    # Price must be above this MA (uptrend confirmation)
    trend_ma_period: int = 50


# ──────────────────────────────────────────────────────────────
# FOREIGN FLOW CONFIRMATION (SECONDARY FILTER)
# ──────────────────────────────────────────────────────────────

@dataclass
class ForeignFlowConfig:
    """
    Confirms that smart money is behind the breakout.
    Uses REAL foreign flow data, not synthetic estimates.
    """
    # Net foreign buy must be positive on at least N of past M days
    lookback_days: int = 5
    min_positive_days: int = 3  # at least 3 of 5 days = net foreign buy

    # Minimum net foreign value (Rp) to count as meaningful
    min_net_foreign_value: float = 0

    # For exit: consecutive days of net foreign selling triggers exit
    exit_consecutive_sell_days: int = 5


# ──────────────────────────────────────────────────────────────
# TECHNICAL FILTERS
# ──────────────────────────────────────────────────────────────

@dataclass
class TechnicalConfig:
    rsi_period: int = 14
    rsi_min: float = 40.0
    rsi_max: float = 75.0   # higher ceiling for breakouts
    macd_fast: int = 12
    macd_slow: int = 26
    macd_signal: int = 9
    price_above_ema: int = 50
    entry_volume_multiplier: float = 1.5


# ──────────────────────────────────────────────────────────────
# ENTRY RULES
# ──────────────────────────────────────────────────────────────

@dataclass
class EntryConfig:
    entry_timing: str = "next_open"
    signal_confirmation_days: int = 1  # breakouts are events, no delay
    max_gap_down_pct: float = 0.02
    min_big_money_score: float = 0.0  # not used in v4


# ──────────────────────────────────────────────────────────────
# POSITION SIZING
# ──────────────────────────────────────────────────────────────

@dataclass
class PositionSizingConfig:
    risk_per_trade: float = 0.02
    atr_period: int = 14
    atr_stop_multiple: float = 2.0
    max_position_pct: float = 0.15
    max_total_exposure: float = 0.80
    max_positions: int = 8
    max_sector_pct: float = 0.30
    settlement_buffer: float = 0.05


# ──────────────────────────────────────────────────────────────
# EXIT RULES
# ──────────────────────────────────────────────────────────────

@dataclass
class ExitConfig:
    stop_loss_pct: float = 0.07
    stop_loss_atr_mult: float = 1.5
    stop_loss_hard_cap: float = 0.08

    trailing_activation_pct: float = 0.08
    trailing_atr_mult: float = 2.0
    trailing_ema: int = 20

    partial_sell_fraction: float = 0.30
    partial_target_pct: float = 0.15

    time_exit_min_gain: float = 0.03
    time_exit_max_days: int = 15

    bear_regime_close_fraction: float = 1.0
    stop_loss_cooldown_days: int = 30
    max_entries_per_day: int = 3

    # Kept for backward compat
    big_money_exit_score: float = 0.0


@dataclass
class BacktestConfig:
    initial_capital: float = 1_000_000_000
    start_date: str = "2021-01-01"
    end_date: str = "2024-12-31"
    risk_free_rate: float = 0.06
    benchmark_ticker: str = "^JKSE"


@dataclass
class ScraperConfig:
    yf_suffix: str = ".JK"
    request_delay: float = 1.0
    max_retries: int = 3
    retry_backoff: float = 2.0
    initial_lookback_days: int = 756
    data_dir: str = "data_raw"


# Backward compat stub — not used in v4 signal logic
@dataclass
class BigMoneyConfig:
    score_entry_threshold: float = 0.0
    score_exit_threshold: float = 0.0
    weight_foreign_flow: float = 0.0
    weight_volume_price: float = 0.0
    weight_broker_summary: float = 0.0
    foreign_consec_days: int = 3
    foreign_vol_threshold: float = 0.10
    volume_spike_multiplier: float = 2.0
    obv_slope_lookback: int = 10
    ad_line_lookback: int = 10
    institutional_brokers: List[str] = field(default_factory=list)
    broker_net_buy_threshold: float = 0.15
    broker_consec_days: int = 3


@dataclass
class FrameworkConfig:
    universe: UniverseConfig = field(default_factory=UniverseConfig)
    regime: MarketRegimeConfig = field(default_factory=MarketRegimeConfig)
    breakout: BreakoutConfig = field(default_factory=BreakoutConfig)
    foreign_flow: ForeignFlowConfig = field(default_factory=ForeignFlowConfig)
    technical: TechnicalConfig = field(default_factory=TechnicalConfig)
    entry: EntryConfig = field(default_factory=EntryConfig)
    sizing: PositionSizingConfig = field(default_factory=PositionSizingConfig)
    exit: ExitConfig = field(default_factory=ExitConfig)
    backtest: BacktestConfig = field(default_factory=BacktestConfig)
    scraper: ScraperConfig = field(default_factory=ScraperConfig)
    big_money: BigMoneyConfig = field(default_factory=BigMoneyConfig)


DEFAULT_CONFIG = FrameworkConfig()
