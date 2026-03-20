"""
IDX Swing Trading Framework — Configuration
=============================================
All tunable parameters, thresholds, and constants in one place.
Conservative defaults chosen for robustness over optimisation.

DISCLAIMER: This framework is for educational and research purposes only.
Past performance does not guarantee future results. Trading involves risk
of loss. Consult a licensed financial advisor before investing.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional
import os

# ──────────────────────────────────────────────────────────────
# 1. GENERAL
# ──────────────────────────────────────────────────────────────

TIMEZONE = "Asia/Jakarta"  # WIB
CURRENCY = "IDR"
DATABASE_URL = os.getenv("IDX_DB_URL", "sqlite:///idx_swing_trader.db")

# IDX lot size — all orders must be multiples of 100 shares
LOT_SIZE = 100

# IDX trading sessions (WIB)
TRADING_HOURS = {
    "pre_open":  ("08:45", "09:00"),
    "session_1": ("09:00", "12:00"),
    "session_2": ("13:30", "16:15"),
}

# ──────────────────────────────────────────────────────────────
# 2. IDX TRANSACTION COSTS
# ──────────────────────────────────────────────────────────────

BUY_COMMISSION = 0.0015     # 0.15 %
SELL_COMMISSION = 0.0025    # 0.25 % (includes 0.1 % final income tax)
SLIPPAGE_TICKS = 1          # assume 1 tick adverse slippage per trade

# IDX tick-size table (effective 2024-02)
# price_band_lower, price_band_upper, tick_size
TICK_SIZE_TABLE = [
    (1,       50,      1),
    (51,      200,     2),
    (201,     500,     5),
    (501,     2_000,   10),
    (2_001,   5_000,   25),
    (5_001,   float("inf"), 50),
]

# Auto-rejection limits (symmetric %)
ARA_ARB_LIMITS = {
    "acceleration_board": 0.35,  # ±35 %
    "regular":           0.25,   # ±25 % (used as default)
    "development_board": 0.35,
}


# ──────────────────────────────────────────────────────────────
# 3. STOCK UNIVERSE & PRE-SCREENING
# ──────────────────────────────────────────────────────────────

@dataclass
class UniverseConfig:
    # Eligible universe: "LQ45", "IDX80", or "CUSTOM"
    index_membership: str = "LQ45"

    # Minimum 20-day average daily trading value (IDR)
    min_avg_daily_value: float = 5_000_000_000  # Rp 5 billion

    # Minimum market cap (IDR)
    min_market_cap: float = 1_000_000_000_000  # Rp 1 trillion

    # Maximum bid-ask spread as % of price (skip if data unavailable)
    max_spread_pct: Optional[float] = 0.02  # 2 %

    # Sectors to exclude (IDX sector codes)
    excluded_sectors: List[str] = field(default_factory=list)


# ──────────────────────────────────────────────────────────────
# 4. MARKET REGIME FILTER (IHSG)
# ──────────────────────────────────────────────────────────────

@dataclass
class MarketRegimeConfig:
    # EMA periods on IHSG daily close
    ema_fast: int = 20
    ema_medium: int = 50
    ema_slow: int = 200

    # Breadth: % of universe stocks above their 50-day MA
    breadth_period: int = 50

    # Regime thresholds
    # BULL  : EMA20 > EMA50 > EMA200  AND  breadth > 60 %
    # BEAR  : EMA20 < EMA50 < EMA200  AND  breadth < 40 %
    # SIDEWAYS : everything else
    breadth_bull_threshold: float = 0.60
    breadth_bear_threshold: float = 0.40

    # Exposure multiplier per regime
    # 1.0 = full exposure, 0.5 = half, 0.0 = cash only
    exposure_multiplier: Dict[str, float] = field(default_factory=lambda: {
        "BULL":     1.0,
        "SIDEWAYS": 0.5,
        "BEAR":     0.0,
    })


# ──────────────────────────────────────────────────────────────
# 5. BIG MONEY / INSTITUTIONAL FLOW DETECTION
# ──────────────────────────────────────────────────────────────

@dataclass
class BigMoneyConfig:
    # --- Method 1: Foreign Flow ---
    # Consecutive days of net foreign buy required
    foreign_consec_days: int = 3
    # Net foreign buy must exceed this fraction of 20-day avg volume
    foreign_vol_threshold: float = 0.10  # 10 %

    # --- Method 2: Volume-Price Analysis ---
    # Volume spike: today's volume > X × 20-day average volume
    volume_spike_multiplier: float = 2.0
    # OBV trend: OBV 10-day slope must be positive & above threshold
    obv_slope_lookback: int = 10
    # Accumulation/Distribution line must be rising over N days
    ad_line_lookback: int = 10

    # --- Method 3: Broker Summary (Institutional Broker Codes) ---
    # Known institutional / foreign broker codes
    institutional_brokers: List[str] = field(default_factory=lambda: [
        "CS", "UB", "YU", "RX", "AK", "CC", "BK",  # foreign
        "PD", "IF", "NI", "KZ", "BW",                # domestic institutional
    ])
    # Institutional broker net buy must exceed this % of daily value
    broker_net_buy_threshold: float = 0.15  # 15 %
    # Minimum days of net institutional accumulation
    broker_consec_days: int = 3

    # --- Scoring Weights ---
    # Each method yields 0.0–1.0; weighted sum produces final score
    weight_foreign_flow: float = 0.35
    weight_volume_price: float = 0.35
    weight_broker_summary: float = 0.30

    # Minimum composite score to trigger "big money detected"
    score_entry_threshold: float = 0.55
    # Score below which we consider distribution (exit signal)
    score_exit_threshold: float = 0.25


# ──────────────────────────────────────────────────────────────
# 6. TECHNICAL CONFIRMATION
# ──────────────────────────────────────────────────────────────

@dataclass
class TechnicalConfig:
    # Price must be above this EMA
    price_above_ema: int = 50

    # RSI range (buy only when RSI is between these values)
    rsi_period: int = 14
    rsi_min: float = 40.0   # not oversold enough to be dangerous
    rsi_max: float = 70.0   # not overbought

    # MACD must be positive (MACD line > signal line)
    macd_fast: int = 12
    macd_slow: int = 26
    macd_signal: int = 9

    # Volume confirmation: entry-day volume ≥ X × 20-day avg
    entry_volume_multiplier: float = 1.2


# ──────────────────────────────────────────────────────────────
# 7. ENTRY RULES
# ──────────────────────────────────────────────────────────────

@dataclass
class EntryConfig:
    # Minimum big-money composite score to enter
    min_big_money_score: float = 0.55

    # Entry timing: "close" = enter at session close, "next_open" = next day open
    entry_timing: str = "next_open"


# ──────────────────────────────────────────────────────────────
# 8. POSITION SIZING & RISK MANAGEMENT
# ──────────────────────────────────────────────────────────────

@dataclass
class PositionSizingConfig:
    # --- Fixed-fractional with ATR adjustment ---
    # Risk per trade as % of portfolio equity
    risk_per_trade: float = 0.02  # 2 %

    # ATR period for volatility calculation
    atr_period: int = 14

    # Stop distance in ATR multiples
    atr_stop_multiple: float = 2.0

    # Position size = (equity × risk_per_trade) / (atr_stop_multiple × ATR)
    # Then round down to nearest LOT_SIZE

    # Maximum single position as % of equity
    max_position_pct: float = 0.15  # 15 %

    # Maximum total portfolio exposure
    max_total_exposure: float = 0.80  # 80 %

    # Maximum concurrent open positions
    max_positions: int = 8

    # Maximum sector concentration
    max_sector_pct: float = 0.30  # 30 %

    # T+2 settlement buffer: reserve this % of equity for settlement
    settlement_buffer: float = 0.05  # 5 %


# ──────────────────────────────────────────────────────────────
# 9. EXIT RULES
# ──────────────────────────────────────────────────────────────

@dataclass
class ExitConfig:
    # --- Initial stop-loss ---
    # whichever is wider: fixed % OR ATR-based
    stop_loss_pct: float = 0.07       # -7 % hard stop
    stop_loss_atr_mult: float = 2.0   # 2 × ATR

    # --- Trailing stop ---
    # Activated after stock reaches this profit %
    trailing_activation_pct: float = 0.10  # +10 %
    # Trail at this ATR multiple below highest close since entry
    trailing_atr_mult: float = 2.5
    # Or trail below this EMA (whichever is tighter)
    trailing_ema: int = 20

    # --- Partial profit taking ---
    # Sell this fraction at the first target
    partial_sell_fraction: float = 0.50  # sell 50 %
    partial_target_pct: float = 0.15     # at +15 %

    # --- Time-based exit ---
    # Exit if stock hasn't moved +X % within Y trading days
    time_exit_min_gain: float = 0.05  # +5 %
    time_exit_max_days: int = 20      # 20 trading days

    # --- Big money exit ---
    # If composite score drops below this, exit
    big_money_exit_score: float = 0.25

    # --- Regime exit ---
    # If market goes BEAR, close this fraction of all positions
    bear_regime_close_fraction: float = 1.0  # close everything


# ──────────────────────────────────────────────────────────────
# 10. BACKTEST
# ──────────────────────────────────────────────────────────────

@dataclass
class BacktestConfig:
    # Starting capital (IDR)
    initial_capital: float = 1_000_000_000  # Rp 1 billion

    # Backtest date range
    start_date: str = "2021-01-01"
    end_date: str = "2024-12-31"

    # Risk-free rate for Sharpe / Sortino (annualised)
    risk_free_rate: float = 0.06  # BI rate ~6 %

    # Benchmark ticker (IHSG)
    benchmark_ticker: str = "^JKSE"


# ──────────────────────────────────────────────────────────────
# 11. DATA SCRAPING
# ──────────────────────────────────────────────────────────────

@dataclass
class ScraperConfig:
    # Yahoo Finance suffix for IDX stocks
    yf_suffix: str = ".JK"

    # Scrape rate-limiting: seconds between requests
    request_delay: float = 1.0
    max_retries: int = 3
    retry_backoff: float = 2.0  # exponential backoff multiplier

    # Historical lookback for initial scrape (trading days)
    initial_lookback_days: int = 756  # ~3 years of trading days

    # Data directory for raw CSV fallback
    data_dir: str = "data_raw"


# ──────────────────────────────────────────────────────────────
# AGGREGATE CONFIG
# ──────────────────────────────────────────────────────────────

@dataclass
class FrameworkConfig:
    universe: UniverseConfig = field(default_factory=UniverseConfig)
    regime: MarketRegimeConfig = field(default_factory=MarketRegimeConfig)
    big_money: BigMoneyConfig = field(default_factory=BigMoneyConfig)
    technical: TechnicalConfig = field(default_factory=TechnicalConfig)
    entry: EntryConfig = field(default_factory=EntryConfig)
    sizing: PositionSizingConfig = field(default_factory=PositionSizingConfig)
    exit: ExitConfig = field(default_factory=ExitConfig)
    backtest: BacktestConfig = field(default_factory=BacktestConfig)
    scraper: ScraperConfig = field(default_factory=ScraperConfig)


# Default instance — import and use directly or create custom
DEFAULT_CONFIG = FrameworkConfig()
