"""
IDX Swing Trading Framework — Configuration v5
=================================================
Breakout + foreign flow + historical resistance + trend-following exit.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional
import os

TIMEZONE = "Asia/Jakarta"
CURRENCY = "IDR"
DATABASE_URL = os.getenv("IDX_DB_URL", "sqlite:///idx_swing_trader.db")
LOT_SIZE = 100

TRADING_HOURS = {
    "pre_open": ("08:45", "09:00"),
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

    # NEW: Minimum stock price filter — exclude junk/penny stocks
    min_stock_price: float = 150.0


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

    # Exp 11: Sector cohort momentum filter
    # Skip entry when the ticker's sector cohort is below its own SMA.
    # Symmetric with Exp 2 IHSG filter (close > MA20), but applied per-sector.
    # See signals/sector_regime.py.
    exp11_sector_filter_enabled: bool = False
    exp11_sector_ma_period: int = 20


@dataclass
class BreakoutConfig:
    """
    Primary entry: breakout above HISTORICAL resistance, not just 20-day high.
    
    NEW in v5: Uses 60-day high as resistance level instead of 20-day.
    This means we only enter when the stock breaks a more significant 
    price level — a real resistance break, not just a minor swing high.
    """
    # Break above N-day highest high (historical resistance)
    breakout_period: int = 60  # 60-day high = ~3 months of resistance (was 20)

    # Volume spike on breakout day
    volume_spike_min: float = 1.5
    volume_spike_max: float = 5.0

    # Price must be above this MA
    trend_ma_period: int = 50

    # Exp 20: replace min_stock_price with ADV (avg daily value) floor — off by default
    exp20_liquidity_floor_enabled: bool = False
    exp20_min_adv: float = 2_000_000_000  # Rp 2bn ADV20



@dataclass
class ForeignFlowConfig:
    lookback_days: int = 5
    min_positive_days: int = 3
    min_net_foreign_value: float = 0
    exit_consecutive_sell_days: int = 5


@dataclass
class TechnicalConfig:
    rsi_period: int = 14
    rsi_min: float = 40.0
    rsi_max: float = 75.0
    macd_fast: int = 12
    macd_slow: int = 26
    macd_signal: int = 9
    price_above_ema: int = 50
    entry_volume_multiplier: float = 1.5


@dataclass
class EntryConfig:
    entry_timing: str = "next_open"
    signal_confirmation_days: int = 1
    max_gap_down_pct: float = 0.02
    max_gap_up_pct: float = 0.07   # skip entry if stock gaps up >7% from signal close
    max_entries_per_week: int = 5  # rolling 10-day entry limit — prevents cluster overtrading
    min_big_money_score: float = 0.0


@dataclass
class PositionSizingConfig:
    risk_per_trade: float = 0.015
    atr_period: int = 14
    atr_stop_multiple: float = 2.0
    max_position_pct: float = 0.12  # 12% max per stock (was 15%)
    max_total_exposure: float = 0.90  # 90% max invested (was 80%)
    max_sector_pct: float = 0.30
    settlement_buffer: float = 0.05
    # max_positions REMOVED — capital allocation is the real limit
    # With 90% max exposure and 12% per stock, natural max is ~7-8 positions
    # But if some positions are small (partial sold or smaller stocks),
    # more positions can fit — just like real trading


@dataclass
class ExitConfig:
    # Stop-loss (only fires AFTER min_hold_days)
    stop_loss_pct: float = 0.07
    stop_loss_atr_mult: float = 1.5
    stop_loss_hard_cap: float = 0.10  # widened to 10% since we hold through early vol

    # NEW: Minimum hold period — stop-loss does NOT fire during this period
    # Data shows trades that survive 5 days have 49% win rate vs 7% for days 1-5
    min_hold_days: int = 5

    # NEW: Emergency stop — even during hold period, exit if loss exceeds this
    # This prevents catastrophic damage from gap-downs during hold period
    emergency_stop_pct: float = 0.12  # -12% = something is seriously wrong (tightened from 0.15)

    # Trailing stop
    trailing_activation_pct: float = 0.08
    trailing_atr_mult: float = 2.0
    trailing_ema: int = 20

    # Partial profit: sell 30% at +15%
    partial_sell_fraction: float = 0.30
    partial_target_pct: float = 0.15

    # NEW: Trend-following exit for high-performers
    # Instead of trailing stop, use MA break as exit signal
    # If stock gained > trend_threshold, switch to trend exit mode:
    # only exit when price closes below trend_exit_ma
    trend_threshold_pct: float = 0.15  # +15% gain triggers trend mode
    trend_exit_ma: int = 10  # exit when close < 10-day MA (short-term trend)

    # Time exit
    time_exit_min_gain: float = 0.03
    time_exit_max_days: int = 15

    # Regime exit
    bear_regime_close_fraction: float = 1.0

    # Cooldown
    stop_loss_cooldown_days: int = 30
    max_entries_per_day: int = 3

    # Compat
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
