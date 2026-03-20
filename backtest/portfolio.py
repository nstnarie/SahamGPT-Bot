"""
Portfolio Management v4
========================
Position sizing, stop-loss with hard cap, trailing stop, foreign flow exit.
"""

import logging
from dataclasses import dataclass, field
from datetime import date
from typing import Dict, List, Optional, Tuple

import numpy as np

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


@dataclass
class PortfolioState:
    cash: float
    positions: Dict[str, Position] = field(default_factory=dict)
    total_equity: float = 0.0

    def update_equity(self, current_prices: Dict[str, float]):
        market_value = sum(
            pos.remaining_shares * current_prices.get(pos.ticker, pos.entry_price)
            for pos in self.positions.values()
        )
        self.total_equity = self.cash + market_value

    @property
    def num_positions(self) -> int:
        return len(self.positions)

    @property
    def invested_pct(self) -> float:
        if self.total_equity <= 0:
            return 0.0
        return 1.0 - (self.cash / self.total_equity)

    def get_sector_exposure(self) -> Dict[str, float]:
        if self.total_equity <= 0:
            return {}
        sector_values: Dict[str, float] = {}
        for pos in self.positions.values():
            sec = pos.sector or "Unknown"
            val = pos.remaining_shares * pos.entry_price
            sector_values[sec] = sector_values.get(sec, 0) + val
        return {s: v / self.total_equity for s, v in sector_values.items()}


class PortfolioManager:

    def __init__(self, sizing_config=None, exit_config=None):
        self.sizing = sizing_config or DEFAULT_CONFIG.sizing
        self.exits = exit_config or DEFAULT_CONFIG.exit

    def calculate_position_size(self, portfolio, entry_price, atr, sector="", regime_exposure_mult=1.0):
        equity = portfolio.total_equity
        if equity <= 0 or entry_price <= 0 or atr <= 0:
            return 0

        risk_amount = equity * self.sizing.risk_per_trade
        stop_distance = atr * self.sizing.atr_stop_multiple
        min_stop_distance = entry_price * self.exits.stop_loss_pct
        stop_distance = max(stop_distance, min_stop_distance)

        raw_shares = risk_amount / stop_distance

        max_position_value = equity * self.sizing.max_position_pct
        raw_shares = min(raw_shares, max_position_value / entry_price)
        raw_shares *= regime_exposure_mult

        current_invested = equity - portfolio.cash
        max_additional = (equity * self.sizing.max_total_exposure) - current_invested
        max_additional -= equity * self.sizing.settlement_buffer
        if max_additional <= 0:
            return 0
        raw_shares = min(raw_shares, max_additional / entry_price)

        if portfolio.num_positions >= self.sizing.max_positions:
            return 0

        sector_exp = portfolio.get_sector_exposure()
        remaining_sector = self.sizing.max_sector_pct - sector_exp.get(sector or "Unknown", 0.0)
        if remaining_sector <= 0:
            return 0
        raw_shares = min(raw_shares, (remaining_sector * equity) / entry_price)

        buy_cost_per_share = entry_price * (1 + 0.0015)
        raw_shares = min(raw_shares, portfolio.cash / buy_cost_per_share)

        # NaN guard
        if raw_shares != raw_shares or raw_shares <= 0:
            return 0

        return round_to_lot(int(raw_shares))

    def calculate_initial_stop(self, entry_price: float, atr: float) -> float:
        """Stop-loss: tighter of -7% or 1.5×ATR, with -8% hard cap."""
        pct_stop = entry_price * (1 - self.exits.stop_loss_pct)
        atr_stop = entry_price - (self.exits.stop_loss_atr_mult * atr)
        initial_stop = max(pct_stop, atr_stop)  # tighter = higher price

        hard_cap_price = entry_price * (1 - self.exits.stop_loss_hard_cap)
        initial_stop = max(initial_stop, hard_cap_price)

        tick = get_tick_size(entry_price)
        return max(initial_stop, tick)

    def update_trailing_stop(self, position, current_close, current_atr):
        profit_pct = (current_close - position.entry_price) / position.entry_price

        if current_close > position.highest_close:
            position.highest_close = current_close

        if profit_pct >= self.exits.trailing_activation_pct:
            position.trailing_active = True

        if not position.trailing_active:
            return position.stop_price

        trail_atr = position.highest_close - (self.exits.trailing_atr_mult * current_atr)
        new_stop = max(position.stop_price, trail_atr)

        if new_stop > position.stop_price:
            position.stop_price = new_stop

        return new_stop

    def check_exit_conditions(self, position, current_close, current_low,
                               current_atr, composite_score, regime, trading_day,
                               ff_consecutive_sell=0):
        """Check all exit conditions. Returns (exit_reason, fraction_to_sell)."""

        # 1. Stop-loss
        if current_low <= position.stop_price:
            return "STOP_LOSS", 1.0

        profit_pct = (current_close - position.entry_price) / position.entry_price

        # 2. Partial profit
        if (not position.partial_sold
                and self.exits.partial_sell_fraction > 0
                and profit_pct >= self.exits.partial_target_pct):
            position.partial_sold = True
            return "PARTIAL_PROFIT", self.exits.partial_sell_fraction

        # 3. Time exit
        if (position.days_held >= self.exits.time_exit_max_days
                and profit_pct < self.exits.time_exit_min_gain):
            return "TIME_EXIT", 1.0

        # 4. Foreign flow exit — 5 consecutive days of net selling
        if ff_consecutive_sell >= 5:
            return "FF_EXIT", 1.0

        # 5. Regime exit
        if regime == "BEAR":
            return "REGIME_EXIT", self.exits.bear_regime_close_fraction

        return "", 0.0
