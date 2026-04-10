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
    # Exp 19: trend leader flag — widens stop to -15%/3×ATR when confirmed uptrend
    trend_leader: bool = False


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
        """
        Calculate position size based on CAPITAL ALLOCATION, not slot counts.
        
        Gates (in order):
          1. Risk budget: 1.5% of equity per trade
          2. Max single position: 12% of equity
          3. Regime adjustment: half size in sideways
          4. Total exposure cap: 90% of equity max invested
          5. Sector cap: 30% of equity per sector
          6. Cash available: can't spend more than you have
        
        No hard position count limit. If you have capital, you can enter.
        This is how real trading works.
        """
        equity = portfolio.total_equity
        if equity <= 0 or entry_price <= 0 or atr <= 0:
            return 0

        # 1. Risk-based sizing
        risk_amount = equity * self.sizing.risk_per_trade
        stop_distance = max(atr * self.sizing.atr_stop_multiple,
                            entry_price * self.exits.stop_loss_pct)
        raw_shares = risk_amount / stop_distance

        # 2. Max single position cap
        raw_shares = min(raw_shares, (equity * self.sizing.max_position_pct) / entry_price)

        # 3. Regime adjustment
        raw_shares *= regime_exposure_mult

        # 4. Total exposure cap — how much more can we invest?
        current_invested = equity - portfolio.cash
        current_exposure_pct = current_invested / equity if equity > 0 else 0
        max_add = (equity * self.sizing.max_total_exposure) - current_invested - (equity * self.sizing.settlement_buffer)
        if max_add <= 0:
            return 0
        raw_shares = min(raw_shares, max_add / entry_price)

        # 5. Sector cap
        se = portfolio.get_sector_exposure()
        remaining = self.sizing.max_sector_pct - se.get(sector or "Unknown", 0.0)
        if remaining <= 0:
            return 0
        raw_shares = min(raw_shares, (remaining * equity) / entry_price)

        # 6. Cash available
        raw_shares = min(raw_shares, portfolio.cash / (entry_price * 1.0015))

        if raw_shares != raw_shares or raw_shares <= 0:
            return 0
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
                               ff_consecutive_sell=0, current_ma10=None,
                               is_foreign_driven=False, acc_score=0,
                               current_ma50=None):
        """
        Exit logic v8:

        1. Emergency stop: -15% at ANY time (even during hold period)
        2. During first 5 days: NO regular stop-loss
        3. HIGH PERFORMERS (+15%): trend exit — close < MA10
        4. Stop-loss: -7% or 1.5xATR, cap -10% (after day 5)
           → Hold extension: if acc_score > 0 on days 6-10, skip stop once —
             brokers are still accumulating, dip is likely temporary
        5. Partial profit: sell 30% at +15%
        6. Time exit: 15 days no +3%
        7. FF exit: 5 consecutive days net foreign sell (ONLY for foreign-driven stocks,
           and ONLY when stock is also losing momentum — not when it's still rising)
        8. Regime exit: BEAR → close all
        """
        profit_pct = (current_close - position.entry_price) / position.entry_price

        # 1. EMERGENCY STOP — always active, even during hold period
        emergency_loss = (current_low - position.entry_price) / position.entry_price
        if emergency_loss <= -self.exits.emergency_stop_pct:
            return "EMERGENCY_STOP", 1.0

        # 2. MINIMUM HOLD PERIOD
        if position.days_held <= self.exits.min_hold_days:
            if (not position.partial_sold
                    and self.exits.partial_sell_fraction > 0
                    and profit_pct >= self.exits.partial_target_pct):
                position.partial_sold = True
                return "PARTIAL_PROFIT", self.exits.partial_sell_fraction
            return "", 0.0

        # === After min_hold_days ===

        # 3. HIGH PERFORMER TREND EXIT
        if position.in_trend_mode and current_ma10 is not None:
            if current_close < current_ma10:
                return "TREND_EXIT", 1.0
            if regime == "BEAR":
                return "REGIME_EXIT", self.exits.bear_regime_close_fraction
            return "", 0.0

        # 4. REGULAR STOP-LOSS
        # Exp 19: trend leaders (≥10 days held, ≥+10% PnL, close > MA50) get a
        # wider stop — max(entry×0.85, entry−3×ATR) — to survive mid-move shakeouts.
        # 86% of 2025 mega-winners had >20% drawdowns mid-move; regular −7% stop
        # cuts them before they recover. Emergency stop (-12%) still fires above this.
        profit_pct_for_leader = (current_close - position.entry_price) / position.entry_price
        above_ma50 = (current_ma50 is None or current_close > current_ma50)
        if (position.days_held >= 10
                and profit_pct_for_leader >= 0.10
                and above_ma50):
            position.trend_leader = True

        if position.trend_leader:
            effective_stop = max(
                position.entry_price * 0.85,
                position.entry_price - 3 * position.entry_atr,
            )
        else:
            effective_stop = position.stop_price

        if current_low <= effective_stop:
            # Hold extension: days 6-10 only — if Asing brokers are still
            # net-accumulating (acc_score > 0), skip the stop once.
            # Rationale: the dip is being bought by institutions → likely temporary.
            # Emergency stop (-15%) already fired above, so this is safe.
            if acc_score > 0 and position.days_held <= 10:
                return "", 0.0
            return "STOP_LOSS", 1.0

        # 5. Partial profit
        if (not position.partial_sold
                and self.exits.partial_sell_fraction > 0
                and profit_pct >= self.exits.partial_target_pct):
            position.partial_sold = True
            return "PARTIAL_PROFIT", self.exits.partial_sell_fraction

        # 6. Time exit — but NOT if stock is still trending up
        # PGAS fix: entered 1860, exited 1895 at day 15 (+1.9% < 3% threshold).
        # Price kept climbing to 2000. The stock wasn't dead — it was slow-building.
        # New rule: only time-exit if price is ALSO below MA10 (trend broken).
        # If price is above MA10, the stock is still in an uptrend — give it more time.
        if (position.days_held >= self.exits.time_exit_max_days
                and profit_pct < self.exits.time_exit_min_gain):
            if current_ma10 is not None and current_close > current_ma10:
                # Stock is above MA10 — still trending up, don't exit yet
                pass
            else:
                # Stock is below MA10 or no MA data — trend broken, exit
                return "TIME_EXIT", 1.0

        # 7. Foreign flow exit — ONLY for foreign-driven stocks
        # AND only when price is also below entry (losing) or below MA10 (weakening)
        # DSSA fix: stock went +78% after FF_EXIT because it's domestic-driven.
        # Even for foreign stocks, if price is still rising, foreign selling
        # might just be profit-taking, not distribution.
        if is_foreign_driven and ff_consecutive_sell >= 5:
            price_weakening = (
                profit_pct < 0  # stock is in the red
                or (current_ma10 is not None and current_close < current_ma10)  # below MA10
            )
            if price_weakening:
                return "FF_EXIT", 1.0

        # 8. Regime exit
        if regime == "BEAR":
            return "REGIME_EXIT", self.exits.bear_regime_close_fraction

        return "", 0.0
