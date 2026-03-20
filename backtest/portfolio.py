"""
Portfolio Management
=====================
Handles position sizing, tracking open positions, and enforcing risk limits.
Uses ATR-based position sizing with fixed-fractional risk.

Position size formula:
    risk_amount = equity × risk_per_trade
    shares = risk_amount / (ATR × atr_stop_multiple)
    shares = round_down_to_lot(shares)
    position_value = shares × entry_price
    if position_value > max_position_pct × equity → reduce
"""

import logging
from dataclasses import dataclass, field
from datetime import date
from typing import Dict, List, Optional, Tuple

import numpy as np

from config import (
    PositionSizingConfig, ExitConfig, DEFAULT_CONFIG, LOT_SIZE,
)
from backtest.costs import (
    compute_buy_cost, compute_sell_proceeds,
    round_to_lot, get_tick_size,
)

logger = logging.getLogger(__name__)


@dataclass
class Position:
    """Represents an open position."""
    ticker: str
    entry_date: date
    entry_price: float          # actual execution price (after slippage)
    shares: int                 # total shares bought
    remaining_shares: int       # after partial sells
    total_cost: float           # total IDR spent (incl. commission)
    stop_price: float           # current stop-loss level
    highest_close: float        # highest close since entry (for trailing stop)
    trailing_active: bool = False  # trailing stop activated?
    partial_sold: bool = False  # partial profit taken?
    sector: str = ""
    entry_atr: float = 0.0     # ATR at entry (for reference)
    days_held: int = 0


@dataclass
class PortfolioState:
    """Current state of the portfolio."""
    cash: float
    positions: Dict[str, Position] = field(default_factory=dict)
    total_equity: float = 0.0  # cash + market value of positions

    def update_equity(self, current_prices: Dict[str, float]):
        """Recalculate total equity based on current prices."""
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
        """Get exposure by sector as fraction of equity."""
        if self.total_equity <= 0:
            return {}
        sector_values: Dict[str, float] = {}
        for pos in self.positions.values():
            sec = pos.sector or "Unknown"
            val = pos.remaining_shares * pos.entry_price  # approximate
            sector_values[sec] = sector_values.get(sec, 0) + val
        return {s: v / self.total_equity for s, v in sector_values.items()}


class PortfolioManager:
    """Manages position sizing and portfolio-level risk constraints."""

    def __init__(
        self,
        sizing_config: PositionSizingConfig = None,
        exit_config: ExitConfig = None,
    ):
        self.sizing = sizing_config or DEFAULT_CONFIG.sizing
        self.exits = exit_config or DEFAULT_CONFIG.exit

    def calculate_position_size(
        self,
        portfolio: PortfolioState,
        entry_price: float,
        atr: float,
        sector: str = "",
        regime_exposure_mult: float = 1.0,
    ) -> int:
        """
        Calculate the number of shares to buy.

        Steps:
          1. Compute risk amount = equity × risk_per_trade
          2. Compute stop distance = ATR × atr_stop_multiple
          3. Shares = risk_amount / stop_distance
          4. Apply max position size cap
          5. Apply regime multiplier
          6. Apply portfolio-level constraints
          7. Round down to lot size

        Returns:
            Number of shares (multiple of LOT_SIZE), or 0 if can't trade.
        """
        equity = portfolio.total_equity
        if equity <= 0 or entry_price <= 0 or atr <= 0:
            return 0

        # Step 1: Risk amount
        risk_amount = equity * self.sizing.risk_per_trade

        # Step 2: Stop distance (per share)
        stop_distance = atr * self.sizing.atr_stop_multiple
        # Also enforce minimum stop of stop_loss_pct
        min_stop_distance = entry_price * self.exits.stop_loss_pct
        stop_distance = max(stop_distance, min_stop_distance)

        # Step 3: Raw shares
        raw_shares = risk_amount / stop_distance

        # Step 4: Max position cap
        max_position_value = equity * self.sizing.max_position_pct
        max_shares_by_value = max_position_value / entry_price
        raw_shares = min(raw_shares, max_shares_by_value)

        # Step 5: Regime adjustment
        raw_shares *= regime_exposure_mult

        # Step 6: Portfolio constraints

        # a. Max total exposure
        current_invested = equity - portfolio.cash
        max_additional = (equity * self.sizing.max_total_exposure) - current_invested
        # Reserve settlement buffer
        max_additional -= equity * self.sizing.settlement_buffer
        if max_additional <= 0:
            return 0
        max_shares_by_exposure = max_additional / entry_price
        raw_shares = min(raw_shares, max_shares_by_exposure)

        # b. Max number of positions
        if portfolio.num_positions >= self.sizing.max_positions:
            return 0

        # c. Sector concentration
        sector_exp = portfolio.get_sector_exposure()
        current_sector_pct = sector_exp.get(sector or "Unknown", 0.0)
        remaining_sector = self.sizing.max_sector_pct - current_sector_pct
        if remaining_sector <= 0:
            return 0
        max_shares_by_sector = (remaining_sector * equity) / entry_price
        raw_shares = min(raw_shares, max_shares_by_sector)

        # d. Can't spend more cash than available
        buy_cost_per_share = entry_price * (1 + 0.0015)  # approx with commission
        max_shares_by_cash = portfolio.cash / buy_cost_per_share
        raw_shares = min(raw_shares, max_shares_by_cash)

        # Step 7: Round to lot
        shares = round_to_lot(int(raw_shares))

        return shares

    def calculate_initial_stop(
        self, entry_price: float, atr: float
    ) -> float:
        """
        Calculate initial stop-loss price.
        Uses the wider of: fixed % stop OR ATR-based stop.
        """
        pct_stop = entry_price * (1 - self.exits.stop_loss_pct)
        atr_stop = entry_price - (self.exits.stop_loss_atr_mult * atr)
        # Use the tighter stop (higher price = closer stop = less risk)
        # Actually the prompt says "whichever is wider" for safety — let's use wider
        initial_stop = min(pct_stop, atr_stop)

        # Ensure stop is positive
        tick = get_tick_size(entry_price)
        return max(initial_stop, tick)

    def update_trailing_stop(
        self, position: Position, current_close: float, current_atr: float
    ) -> float:
        """
        Update trailing stop for a position.

        Trailing activates once profit reaches trailing_activation_pct.
        Trail = highest_close - (trailing_atr_mult × ATR)
        New stop = max(old_stop, trail_level)  — stop only moves up
        """
        profit_pct = (current_close - position.entry_price) / position.entry_price

        # Update highest close
        if current_close > position.highest_close:
            position.highest_close = current_close

        # Activate trailing if profit threshold reached
        if profit_pct >= self.exits.trailing_activation_pct:
            position.trailing_active = True

        if not position.trailing_active:
            return position.stop_price

        # Compute trailing stop level
        trail_atr = position.highest_close - (self.exits.trailing_atr_mult * current_atr)

        # EMA-based trailing stop (using highest_close as proxy — in real use
        # you'd pass the EMA value; here we use a simpler approach)
        # trail_ema would come from the technical DataFrame

        # New stop = max of current stop and trailing level (never move down)
        new_stop = max(position.stop_price, trail_atr)

        if new_stop > position.stop_price:
            logger.debug(
                f"{position.ticker}: Trailing stop raised "
                f"{position.stop_price:.0f} → {new_stop:.0f}"
            )

        position.stop_price = new_stop
        return new_stop

    def check_exit_conditions(
        self,
        position: Position,
        current_close: float,
        current_low: float,
        current_atr: float,
        composite_score: float,
        regime: str,
        trading_day: int,
    ) -> Tuple[str, float]:
        """
        Check all exit conditions for a position.

        Returns:
            (exit_reason, fraction_to_sell)
            exit_reason: "" if no exit, else reason string
            fraction_to_sell: 0.0 to 1.0
        """
        # 1. Stop-loss hit (use low price to check if stop was breached)
        if current_low <= position.stop_price:
            return "STOP_LOSS", 1.0

        # 2. Partial profit taking
        profit_pct = (current_close - position.entry_price) / position.entry_price
        if (
            not position.partial_sold
            and profit_pct >= self.exits.partial_target_pct
        ):
            position.partial_sold = True
            return "PARTIAL_PROFIT", self.exits.partial_sell_fraction

        # 3. Time-based exit
        if (
            position.days_held >= self.exits.time_exit_max_days
            and profit_pct < self.exits.time_exit_min_gain
        ):
            return "TIME_EXIT", 1.0

        # 4. Big money distribution signal
        if composite_score < self.exits.big_money_exit_score:
            return "BIG_MONEY_EXIT", 1.0

        # 5. Bear regime exit
        if regime == "BEAR":
            return "REGIME_EXIT", self.exits.bear_regime_close_fraction

        return "", 0.0
