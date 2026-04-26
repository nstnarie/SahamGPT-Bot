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


@dataclass
class BreakoutConfig:
    """
    Primary entry: breakout above recent high.

    v10 mega-winner rebuild: Uses 20-day high (was 60).
    Step 2 analysis showed N=20 catches 100% of mega-winners at median 13d
    after trough (18.9% missed), vs N=60 catching 96.4% at 34d (30.2% missed).
    """
    # Break above N-day highest high
    breakout_period: int = 20  # 20-day high (was 60 in v5)

    # Volume spike on breakout day
    volume_spike_min: float = 1.5
    volume_spike_max: float = 5.0

    # Price must be above this MA
    trend_ma_period: int = 50


@dataclass
class ForeignFlowConfig:
    lookback_days: int = 5
    min_positive_days: int = 3
    min_net_foreign_value: float = 0
    exit_consecutive_sell_days: int = 5

    # Step 7: KSEI hard filter — block entry when strong foreign outflow
    # ksei_net_5d < -5B IDR → 50 trades blocked, 22% WR, 0 big winners lost
    min_ksei_net_5d: float = -5_000_000_000.0
    use_ksei_filter: bool = True


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
    max_entries_per_week: int = 6  # rolling 10-day entry limit (Step 8: 6 is sweet spot — PF 1.40/+6.4% in 2024, PF 1.75/+14.9% in 2025)
    min_big_money_score: float = 0.0

    # Step 8: Circuit breaker — pause entries after consecutive losses
    # Set to 0 to disable. After N losses in a row, skip next M signal days.
    circuit_breaker_losses: int = 0  # disabled — see note below
    circuit_breaker_pause: int = 0
    # Note: CB(4,5) tested well in trade-log simulation but worsened actual
    # backtest because skipping entries changes capital allocation cascade.
    # The trades that get "replaced" by later entries have different outcomes.


@dataclass
class EntryFilterConfig:
    """Phase B entry quality filters — reduce false breakout entries."""
    # Block entries on stocks >40% below 52-week high (structural decline)
    max_dist_from_52w_high: float = -40.0
    # Extreme pullback filter: block entry if breakout_strength < -8% on entry day (T+1).
    # Analysis (Step 11): safe threshold — blocks 4 trades/year, 0 big winners lost cross-year.
    # PF improvement: 1.34→1.46 (2024), 1.53→1.82 (2025).
    # Applied at ENGINE entry time (T+1 open), not signal day (T), because on signal day
    # breakout_strength is always > 0 by definition of the breakout condition.
    min_breakout_strength: float = -8.0
    # Enable/disable each filter independently (set False to roll back)
    use_52w_filter: bool = True
    use_breakout_strength_filter: bool = True

    # Step 7: new hard filters (confirmed 0 big winners blocked)
    # Block if stock is >10% below 200MA (structural downtrend, d=+0.402)
    min_price_vs_ma200: float = -10.0
    use_ma200_filter: bool = True
    # Block if ATR% < 1.75% (insufficient volatility to generate big moves, d=+0.360)
    min_atr_pct: float = 1.75
    use_atr_filter: bool = True

    # Step 18: ff-price correlation filter — block stocks where foreign flow drives the price.
    # Replaces old fp_ratio volume filter (was 0.45). Correlation computed over 2023-2025 data.
    # corr >= 0.30 blocks 18 stocks: BBRI, BBCA, BMRI, AMAN, ANTM, PSAB, ASII, BBNI,
    # PGAS, UNVR, TLKM, BRIS, GOTO, PTPP, GJTL, UNTR, INDF, DEWA.
    # Result vs old filter: 2024 +4.8% better (PTRO captured as new BW), 2025 -37.2%
    # (EMTK capital diluted), 2023 flat. Rationale: correlation measures actual price
    # influence, not just volume participation — DSSA/TPIA/BREN/AMMN now allowed.
    max_fp_ratio: float = 0.30
    use_fp_filter: bool = True

    # Combined BS/TBA filter (Step 11): block when breakout faded AND big money selling.
    # BS-/TBA- quadrant: 0 big winners in 2024+2025, ~19% WR, ~10 quick failures.
    # PF improvement: 1.49→2.48 (2024), 2.00→2.54 (2025) — blocks 11+9 trades, 0 BW lost.
    # No-op in CI (top_broker_acc=0 when broker DB absent → tba<0 never fires).
    use_combined_bs_tba_filter: bool = True

    # Step 15: False breakout filter — block when stock is just above MA200 (0-10%)
    # AND breakout_strength < 0 (price gapped down below breakout level at T+1 open).
    # Analysis (Step 15, 3-year): 43 trades, 20.9% WR, 0 big winners blocked.
    # Net PnL of blocked trades: -103.8M. Consistent across all 3 years.
    # Intuition: stock in "neutral zone" near MA200 + failed breakout = textbook false breakout.
    # Applied at ENGINE entry time (T+1 open), same as min_breakout_strength filter.
    max_price_vs_ma200_for_bs_filter: float = 10.0   # only applies when price_vs_ma200 < this
    use_ma200_bs_combined_filter: bool = True

    # Step 16: Sector blocking — block sectors with 0 big winners across 3 years.
    # Consumer Cyclical: 23 trades, 43.5% WR, 0 BW
    # Financial Services: 18 trades, 38.9% WR, 0 BW
    # Industrials: 25 trades, 28.0% WR, 0 BW
    blocked_sectors: List[str] = field(default_factory=lambda: [
        "Consumer Cyclical", "Financial Services", "Industrials"
    ])
    use_sector_filter: bool = True
    # Step 17: allow entry in blocked sectors when signal is exceptionally strong
    sector_override_min_bs: float = 5.0    # breakout_strength > this
    sector_override_min_vol: float = 3.0   # vol_ratio > this
    use_sector_override: bool = True


@dataclass
class SignalRankingConfig:
    """
    Step 7: Composite signal quality score for ranking pending entries.

    Replaces vol_ratio (d=0.071, useless) with a weighted combination of
    indicators confirmed via Cohen's d analysis on 803 trades (2021-2025).
    Higher score = higher priority entry when capital is limited.
    """
    # Feature weights (must sum to 1.0)
    weight_price_vs_ma200: float = 0.30   # d=+0.402 — strongest
    weight_breakout_strength: float = 0.20  # d=+0.266
    weight_atr_pct: float = 0.20           # d=+0.360
    weight_prior_return_5d: float = 0.15   # d=+0.358
    weight_rsi: float = 0.15              # d=+0.328

    # Rolling window for within-ticker percentile normalization
    percentile_window: int = 60


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

    # Minimum hold period — stop-loss does NOT fire during this period
    # Kept at 5: trades that survive 5 days have 49% WR vs 7% for days 1-5.
    # Step 8 tested min_hold=3 but it caused 33 noise exits on day 4 (-90M).
    min_hold_days: int = 5

    # Emergency stop — even during hold period, exit if loss exceeds this
    emergency_stop_pct: float = 0.12

    # Trailing stop
    trailing_activation_pct: float = 0.08
    trailing_atr_mult: float = 2.0
    trailing_ema: int = 20

    # Partial profit: sell 30% at +15%
    partial_sell_fraction: float = 0.30
    partial_target_pct: float = 0.10

    # NEW: Trend-following exit for high-performers
    # Instead of trailing stop, use MA break as exit signal
    # If stock gained > trend_threshold, switch to trend exit mode:
    # only exit when price closes below trend_exit_ma
    trend_threshold_pct: float = 0.15  # +15% gain triggers trend mode
    trend_exit_ma: int = 10  # exit when close < N-day MA (short-term trend)

    # Step 16: Trend exit variants for mega-winner retention
    trend_exit_confirm_days: int = 1  # consecutive closes below MA to exit (1=immediate, 2=2-day confirm)
    trend_exit_ma_big_winner: int = 20  # wider MA for positions with gain >= threshold below
    trend_big_winner_threshold: float = 0.3  # gain threshold to switch to wider MA
    use_hwm_for_ma_switch: bool = False  # Step 17: use max unrealized gain (not current) for MA switch

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
class PyramidConfig:
    """
    Position pyramiding: add to winners when they break new resistance.

    Only fires when:
      1. Position is already in trend mode (profit >= +15%)
      2. A new breakout signal fires for the held ticker
      3. Maximum pyramid count not yet reached

    Analysis (Step 12): 61% of big winners fire additional breakout signals
    during the hold period. First add typically appears at +20-57% from entry.
    Simulation: ~+27M IDR theoretical upside across 2024+2025.
    """
    enable_pyramiding: bool = True
    max_adds: int = 2                  # max add-ons per position (initial + 2 adds)
    add_size_fraction: float = 0.50    # each add = 50% of original position size
    min_profit_to_add: float = 0.15    # must be +15% (trend mode) before adding
    use_new_high_trigger: bool = True  # Step 13: also pyramid on new 20d high (no vol req)
                                       # Catches slow grinders (PTRO +42% 2024: 0 adds
                                       # despite 40d hold — no volume spike ever fired)


@dataclass
class FrameworkConfig:
    universe: UniverseConfig = field(default_factory=UniverseConfig)
    regime: MarketRegimeConfig = field(default_factory=MarketRegimeConfig)
    breakout: BreakoutConfig = field(default_factory=BreakoutConfig)
    foreign_flow: ForeignFlowConfig = field(default_factory=ForeignFlowConfig)
    technical: TechnicalConfig = field(default_factory=TechnicalConfig)
    entry: EntryConfig = field(default_factory=EntryConfig)
    entry_filter: EntryFilterConfig = field(default_factory=EntryFilterConfig)
    ranking: SignalRankingConfig = field(default_factory=SignalRankingConfig)
    sizing: PositionSizingConfig = field(default_factory=PositionSizingConfig)
    exit: ExitConfig = field(default_factory=ExitConfig)
    backtest: BacktestConfig = field(default_factory=BacktestConfig)
    scraper: ScraperConfig = field(default_factory=ScraperConfig)
    big_money: BigMoneyConfig = field(default_factory=BigMoneyConfig)
    pyramid: PyramidConfig = field(default_factory=PyramidConfig)


DEFAULT_CONFIG = FrameworkConfig()
