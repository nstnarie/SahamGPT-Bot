"""
Portfolio Management v5
========================
- 5-day minimum hold before stop fires (kills 60% of noise deaths)
- Trend-following exit for high performers (don't sell EMTK too early)
- Emergency stop at -15% even during hold period
"""

import logging
from dataclasses import dataclass, field
from datetime import date
from typing import Dict, Tuple

from config import PositionSizingConfig, ExitConfig, DEFAULT_CONFIG, LOT_SIZE
from backtest.costs import compute_buy_cost, compute_sell_proceeds, round_to_lot, get_tick_size

logger = logging.getLogger(__name__)


@dataclass
class Position:
    ticker: str
    entry_date: date
    entry_price: float
    shares: int
    remaining_shares: int
    total_cost: float
    stop_price: float
    highest_close: float
    trailing_active: bool = False
    partial_sold: bool = False
    sector: str = ""
    entry_atr: float = 0.0
    days_held: int = 0
    # NEW: track if this position is in "trend mode" (high performer)
    in_trend_mode: bool = False


@dataclass
class PortfolioState:
    cash: float
    positions: Dict[str, Position] = field(default_factory=dict)
    total_equity: float = 0.0

    def update_equity(self, current_prices):
        market_value = sum(
            pos.remaining_shares * current_prices.get(pos.ticker, pos.entry_price)
            for pos in self.positions.values()
        )
        self.total_equity = self.cash + market_value

    @property
    def num_positions(self): return len(self.positions)

    @property
    def invested_pct(self):
        return 1.0 - (self.cash / self.total_equity) if self.total_equity > 0 else 0.0

    def get_sector_exposure(self):
        if self.total_equity <= 0: return {}
        se = {}
        for pos in self.positions.values():
            s = pos.sector or "Unknown"
            se[s] = se.get(s, 0) + pos.remaining_shares * pos.entry_price
        return {s: v / self.total_equity for s, v in se.items()}


class PortfolioManager:

    def __init__(self, sizing_config=None, exit_config=None):
        self.sizing = sizing_config or DEFAULT_CONFIG.sizing
        self.exits = exit_config or DEFAULT_CONFIG.exit

    def calculate_position_size(self, portfolio, entry_price, atr,
                                 sector="", regime_exposure_mult=1.0):
        equity = portfolio.total_equity
        if equity <= 0 or entry_price <= 0 or atr <= 0:
            return 0

        risk_amount = equity * self.sizing.risk_per_trade
        stop_distance = max(atr * self.sizing.atr_stop_multiple,
                            entry_price * self.exits.stop_loss_pct)
        raw_shares = risk_amount / stop_distance
        raw_shares = min(raw_shares, (equity * self.sizing.max_position_pct) / entry_price)
        raw_shares *= regime_exposure_mult

        current_invested = equity - portfolio.cash
        max_add = (equity * self.sizing.max_total_exposure) - current_invested - (equity * self.sizing.settlement_buffer)
        if max_add <= 0: return 0
        raw_shares = min(raw_shares, max_add / entry_price)

        if portfolio.num_positions >= self.sizing.max_positions: return 0

        se = portfolio.get_sector_exposure()
        remaining = self.sizing.max_sector_pct - se.get(sector or "Unknown", 0.0)
        if remaining <= 0: return 0
        raw_shares = min(raw_shares, (remaining * equity) / entry_price)
        raw_shares = min(raw_shares, portfolio.cash / (entry_price * 1.0015))

        if raw_shares != raw_shares or raw_shares <= 0: return 0
        return round_to_lot(int(raw_shares))

    def calculate_initial_stop(self, entry_price, atr):
        pct_stop = entry_price * (1 - self.exits.stop_loss_pct)
        atr_stop = entry_price - (self.exits.stop_loss_atr_mult * atr)
        initial = max(pct_stop, atr_stop)
        hard_cap = entry_price * (1 - self.exits.stop_loss_hard_cap)
        initial = max(initial, hard_cap)
        return max(initial, get_tick_size(entry_price))

    def update_trailing_stop(self, position, current_close, current_atr):
        profit_pct = (current_close - position.entry_price) / position.entry_price

        if current_close > position.highest_close:
            position.highest_close = current_close

        if profit_pct >= self.exits.trailing_activation_pct:
            position.trailing_active = True

        # Check if position enters trend mode (high performer)
        if profit_pct >= self.exits.trend_threshold_pct:
            position.in_trend_mode = True

        if not position.trailing_active:
            return position.stop_price

        trail = position.highest_close - (self.exits.trailing_atr_mult * current_atr)
        new_stop = max(position.stop_price, trail)
        if new_stop > position.stop_price:
            position.stop_price = new_stop
        return new_stop

    def check_exit_conditions(self, position, current_close, current_low,
                               current_atr, composite_score, regime, trading_day,
                               ff_consecutive_sell=0, current_ma10=None):
        """
        Exit logic v5:
        
        1. Emergency stop: -15% at ANY time (even during hold period)
        2. During first 5 days: NO regular stop-loss (let breakout develop)
        3. After 5 days: regular stop-loss active
        4. HIGH PERFORMERS (gained > 15%): switch to trend exit — 
           only sell when price closes below MA10 (short-term trend break)
           This keeps you in stocks like EMTK that are running hard.
        5. Time exit, FF exit, regime exit as before
        """
        profit_pct = (current_close - position.entry_price) / position.entry_price

        # 1. EMERGENCY STOP — always active, even during hold period
        # If a stock drops -15%, something is seriously wrong — get out
        emergency_loss = (current_low - position.entry_price) / position.entry_price
        if emergency_loss <= -self.exits.emergency_stop_pct:
            return "EMERGENCY_STOP", 1.0

        # 2. MINIMUM HOLD PERIOD — no regular stop during first N days
        # Data shows: days 1-5 = 7% win rate, days 6+ = 49% win rate
        if position.days_held <= self.exits.min_hold_days:
            # Only emergency stop can fire during this period
            # But still check for partial profit (good news is always welcome)
            if (not position.partial_sold
                    and self.exits.partial_sell_fraction > 0
                    and profit_pct >= self.exits.partial_target_pct):
                position.partial_sold = True
                return "PARTIAL_PROFIT", self.exits.partial_sell_fraction
            return "", 0.0

        # === After min_hold_days, full exit logic applies ===

        # 3. HIGH PERFORMER TREND EXIT
        # If stock gained > 15%, switch to trend-following mode:
        # Don't use stop-loss — only exit when uptrend breaks (close < MA10)
        if position.in_trend_mode and current_ma10 is not None:
            if current_close < current_ma10:
                return "TREND_EXIT", 1.0
            # In trend mode, don't check regular stop — let it ride
            # But still check regime exit
            if regime == "BEAR":
                return "REGIME_EXIT", self.exits.bear_regime_close_fraction
            return "", 0.0

        # 4. REGULAR STOP-LOSS (only after hold period, non-trend-mode)
        if current_low <= position.stop_price:
            return "STOP_LOSS", 1.0

        # 5. Partial profit
        if (not position.partial_sold
                and self.exits.partial_sell_fraction > 0
                and profit_pct >= self.exits.partial_target_pct):
            position.partial_sold = True
            return "PARTIAL_PROFIT", self.exits.partial_sell_fraction

        # 6. Time exit
        if (position.days_held >= self.exits.time_exit_max_days
                and profit_pct < self.exits.time_exit_min_gain):
            return "TIME_EXIT", 1.0

        # 7. Foreign flow exit
        if ff_consecutive_sell >= 5:
            return "FF_EXIT", 1.0

        # 8. Regime exit
        if regime == "BEAR":
            return "REGIME_EXIT", self.exits.bear_regime_close_fraction

        return "", 0.0
