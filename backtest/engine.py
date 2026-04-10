"""
Backtesting Engine v4 — Breakout + Foreign Flow
=================================================
Event-driven backtester using the new breakout signal engine.
"""

import logging
from dataclasses import dataclass
from datetime import date
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from config import FrameworkConfig, DEFAULT_CONFIG
from backtest.portfolio import PortfolioManager, PortfolioState, Position
from backtest.costs import compute_buy_cost, compute_sell_proceeds, round_to_lot
from backtest.metrics import compute_all_metrics, format_metrics_report
from signals.signal_combiner import SignalCombiner

logger = logging.getLogger(__name__)


@dataclass
class Trade:
    ticker: str
    entry_date: date
    exit_date: date
    entry_price: float
    exit_price: float
    shares: int
    direction: str = "LONG"
    entry_cost: float = 0.0
    exit_proceeds: float = 0.0
    pnl: float = 0.0
    pnl_pct: float = 0.0
    holding_days: int = 0
    exit_reason: str = ""
    entry_signal_score: float = 0.0
    sector: str = ""


class BacktestEngine:

    def __init__(self, config: FrameworkConfig = DEFAULT_CONFIG):
        self.config = config
        self.signal_combiner = SignalCombiner(config)
        self.portfolio_mgr = PortfolioManager(config.sizing, config.exit)

    def run(self, universe_prices, ihsg_df, foreign_flows=None,
            broker_data=None, stock_sectors=None):

        foreign_flows = foreign_flows or {}
        broker_data = broker_data or {}
        stock_sectors = stock_sectors or {}

        initial_capital = self.config.backtest.initial_capital
        start_date = pd.Timestamp(self.config.backtest.start_date)
        end_date = pd.Timestamp(self.config.backtest.end_date)

        # Pre-compute signals for all stocks
        logger.info("Pre-computing signals for all stocks...")
        all_signals = self.signal_combiner.generate_signals_universe(
            universe_prices, ihsg_df, foreign_flows, broker_data,
            stock_sectors=stock_sectors,
        )

        # Build trading calendar
        all_dates = set()
        for df in universe_prices.values():
            if not df.empty:
                all_dates.update(df.index)
        if not ihsg_df.empty:
            all_dates.update(ihsg_df.index)

        trading_dates = sorted([d for d in all_dates if start_date <= d <= end_date])

        if not trading_dates:
            logger.error("No trading dates in the specified range")
            return pd.Series(dtype=float), pd.DataFrame(), {}

        logger.info(f"Backtesting {len(trading_dates)} trading days "
                     f"from {trading_dates[0]} to {trading_dates[-1]}")

        # Initialise
        portfolio = PortfolioState(cash=initial_capital, total_equity=initial_capital)
        equity_history = {}
        completed_trades: List[Trade] = []
        pending_entries: Dict[str, float] = {}
        a_tier_pending: Dict[str, float] = {}   # Exp 18: top-2 strength signals, bypass cluster + Exp12
        cooldown_until: Dict[str, object] = {}
        recent_entry_dates: List[object] = []  # rolling window for cluster limit
        consecutive_losses = 0          # Exp 12: consecutive loss counter
        throttle_until = None           # Exp 12: date when 2-entry cap expires

        for i, current_date in enumerate(trading_dates):
            current_prices = {}
            current_data = {}
            for ticker, df in universe_prices.items():
                if current_date in df.index:
                    row = df.loc[current_date]
                    current_prices[ticker] = row["close"]
                    current_data[ticker] = row

            portfolio.update_equity(current_prices)

            # ── 1. Execute pending entries ──
            if pending_entries or a_tier_pending:
                max_entries = self.config.exit.max_entries_per_day
                entries_today = 0

                # Rolling 10-day cluster limit: prevent overtrading during fake breakout weeks
                lookback = 10
                recent_cutoff_idx = max(0, i - lookback)
                recent_cutoff_date = trading_dates[recent_cutoff_idx]
                recent_count = sum(1 for d in recent_entry_dates if d >= recent_cutoff_date)
                # Exp 12: after 3 consecutive losses, cap new entries at 2 for 10 trading days
                throttled = throttle_until is not None and current_date < throttle_until
                max_week = 2 if throttled else self.config.entry.max_entries_per_week
                cluster_blocked = (recent_count >= max_week)

                # Exp 18: A-tier bypasses cluster limit and Exp 12 throttle.
                # Normal entries are skipped when cluster is blocked.
                candidates = sorted(a_tier_pending.items(), key=lambda x: x[1], reverse=True)
                if not cluster_blocked:
                    candidates = candidates + sorted(pending_entries.items(), key=lambda x: x[1], reverse=True)

                for ticker, signal_score in candidates:
                    if entries_today >= max_entries:
                        break

                    # Cooldown check — not bypassed even for A-tier
                    if ticker in cooldown_until and current_date < cooldown_until[ticker]:
                        continue

                    if ticker in current_data and ticker not in portfolio.positions:
                        row = current_data[ticker]
                        open_price = row.get("open", row["close"])

                        # Gap filter (down and up)
                        if i > 0:
                            prev_date = trading_dates[i - 1]
                            ticker_df = universe_prices.get(ticker)
                            if ticker_df is not None and prev_date in ticker_df.index:
                                prev_close = ticker_df.loc[prev_date]["close"]
                                if prev_close > 0:
                                    gap_pct = (open_price - prev_close) / prev_close
                                    if gap_pct < -self.config.entry.max_gap_down_pct:
                                        continue
                                    # Gap-up rejection: stock gapped up >7% at open
                                    # means we're entering at euphoric prices after
                                    # signal fired — high rejection risk (e.g. EMTK Oct 2)
                                    if gap_pct > self.config.entry.max_gap_up_pct:
                                        continue

                        sig_df = all_signals.get(ticker)
                        atr = 0.0
                        if sig_df is not None and current_date in sig_df.index:
                            atr = sig_df.loc[current_date].get("atr", 0)
                        if atr <= 0:
                            atr = open_price * 0.03

                        regime = "SIDEWAYS"
                        exposure_mult = 0.5
                        if sig_df is not None and current_date in sig_df.index:
                            regime = sig_df.loc[current_date].get("regime", "SIDEWAYS")
                            exposure_mult = sig_df.loc[current_date].get("exposure_mult", 0.5)

                        sector = stock_sectors.get(ticker, "")

                        shares = self.portfolio_mgr.calculate_position_size(
                            portfolio, open_price, atr, sector, exposure_mult,
                        )

                        if shares >= 100:
                            buy = compute_buy_cost(open_price, shares)
                            if buy["total_cost"] <= portfolio.cash:
                                stop = self.portfolio_mgr.calculate_initial_stop(
                                    buy["exec_price"], atr,
                                )
                                pos = Position(
                                    ticker=ticker,
                                    entry_date=current_date.date() if hasattr(current_date, 'date') else current_date,
                                    entry_price=buy["exec_price"],
                                    shares=shares,
                                    remaining_shares=shares,
                                    total_cost=buy["total_cost"],
                                    stop_price=stop,
                                    highest_close=buy["exec_price"],
                                    sector=sector,
                                    entry_atr=atr,
                                )
                                portfolio.positions[ticker] = pos
                                portfolio.cash -= buy["total_cost"]
                                entries_today += 1
                                recent_entry_dates.append(current_date)

                pending_entries.clear()
                a_tier_pending.clear()

            # ── 2. Check exits ──
            tickers_to_exit = []
            for ticker, pos in list(portfolio.positions.items()):
                if ticker not in current_data:
                    continue

                row = current_data[ticker]
                sig_df = all_signals.get(ticker)

                composite_score = 0.5
                regime = "SIDEWAYS"
                atr = pos.entry_atr
                ff_consecutive_sell = 0

                if sig_df is not None and current_date in sig_df.index:
                    sig_row = sig_df.loc[current_date]
                    regime = sig_row.get("regime", "SIDEWAYS")
                    atr = sig_row.get("atr", atr)
                    ff_consecutive_sell = int(sig_row.get("ff_consecutive_sell", 0))

                # Get MA10, is_foreign_driven, and accumulation score for exit logic
                current_ma10 = None
                is_foreign_driven = False
                acc_score = 0
                if sig_df is not None and current_date in sig_df.index:
                    current_ma10 = sig_df.loc[current_date].get("ma_10", None)
                    is_foreign_driven = bool(sig_df.loc[current_date].get("is_foreign_driven", False))
                    acc_score = float(sig_df.loc[current_date].get("accumulation_score", 0))

                self.portfolio_mgr.update_trailing_stop(pos, row["close"], atr)
                pos.days_held += 1

                exit_reason, fraction = self.portfolio_mgr.check_exit_conditions(
                    pos, row["close"], row["low"], atr,
                    composite_score, regime, pos.days_held,
                    ff_consecutive_sell=ff_consecutive_sell,
                    current_ma10=current_ma10,
                    is_foreign_driven=is_foreign_driven,
                    acc_score=acc_score,
                )

                if exit_reason and fraction > 0:
                    shares_to_sell = round_to_lot(int(pos.remaining_shares * fraction))
                    if shares_to_sell < 100:
                        shares_to_sell = pos.remaining_shares

                    if exit_reason == "STOP_LOSS":
                        exit_price = pos.stop_price
                    elif exit_reason == "EMERGENCY_STOP":
                        # Emergency: use the hard cap price, not the low
                        exit_price = pos.entry_price * (1 - self.config.exit.emergency_stop_pct)
                    else:
                        exit_price = row["close"]

                    sell = compute_sell_proceeds(exit_price, shares_to_sell)
                    portfolio.cash += sell["net_proceeds"]
                    pos.remaining_shares -= shares_to_sell

                    entry_cost_fraction = pos.total_cost * (shares_to_sell / pos.shares)
                    pnl = sell["net_proceeds"] - entry_cost_fraction

                    trade = Trade(
                        ticker=ticker,
                        entry_date=pos.entry_date,
                        exit_date=current_date.date() if hasattr(current_date, 'date') else current_date,
                        entry_price=pos.entry_price,
                        exit_price=sell["exec_price"],
                        shares=shares_to_sell,
                        entry_cost=entry_cost_fraction,
                        exit_proceeds=sell["net_proceeds"],
                        pnl=pnl,
                        pnl_pct=(pnl / entry_cost_fraction * 100) if entry_cost_fraction > 0 else 0,
                        holding_days=pos.days_held,
                        exit_reason=exit_reason,
                        sector=pos.sector,
                    )
                    completed_trades.append(trade)

                    # Cooldown after stop-loss or trend exit.
                    # TREND_EXIT: stock just made a big move (+15%+) — rest before re-entry.
                    # Pattern 2: EMTK re-entered 17 trading days after TREND_EXIT → emergency stop.
                    if exit_reason in ("STOP_LOSS", "TREND_EXIT"):
                        cooldown_days = self.config.exit.stop_loss_cooldown_days
                        future_idx = min(i + cooldown_days, len(trading_dates) - 1)
                        cooldown_until[ticker] = trading_dates[future_idx]

                    if pos.remaining_shares <= 0:
                        tickers_to_exit.append(ticker)
                        # Exp 12: track consecutive losses on fully closed positions
                        if pnl < 0:
                            consecutive_losses += 1
                            if consecutive_losses >= 3:
                                throttle_until = trading_dates[min(i + 10, len(trading_dates) - 1)]
                                consecutive_losses = 0
                        else:
                            consecutive_losses = 0

            for t in tickers_to_exit:
                del portfolio.positions[t]

            # ── 3. Generate entry signals ──
            # Exp 18: compute strength score for each BUY signal, pick top 2 as A-tier.
            # A-tier will bypass cluster limit and Exp 12 throttle in Step 1.
            buy_candidates: Dict[str, tuple] = {}  # ticker -> (vol_ratio, strength)
            for ticker, sig_df in all_signals.items():
                if ticker in portfolio.positions:
                    continue
                if sig_df is None or sig_df.empty:
                    continue
                if current_date not in sig_df.index:
                    continue

                sig_row = sig_df.loc[current_date]
                if sig_row.get("signal") == "BUY":
                    vol_r = float(sig_row.get("vol_ratio", 1.0))
                    close = float(sig_row.get("close", 0))
                    high_nd = float(sig_row.get("high_Nd", 0))
                    strength = vol_r * (close / high_nd - 1) if high_nd > 0 else 0.0
                    buy_candidates[ticker] = (vol_r, max(strength, 0.0))

            if buy_candidates:
                sorted_by_strength = sorted(
                    buy_candidates.items(), key=lambda x: x[1][1], reverse=True
                )
                a_tier_set = {t for t, _ in sorted_by_strength[:2]}
                for ticker, (vol_r, strength) in buy_candidates.items():
                    if ticker in a_tier_set:
                        a_tier_pending[ticker] = strength
                    else:
                        pending_entries[ticker] = vol_r

            # ── 4. Record equity ──
            portfolio.update_equity(current_prices)
            equity_history[current_date] = portfolio.total_equity

        # Build results
        equity_curve = pd.Series(equity_history, name="equity")
        equity_curve.index = pd.DatetimeIndex(equity_curve.index)

        trade_log = pd.DataFrame([{
            "ticker": t.ticker, "entry_date": t.entry_date, "exit_date": t.exit_date,
            "entry_price": t.entry_price, "exit_price": t.exit_price,
            "shares": t.shares, "entry_cost": t.entry_cost,
            "exit_proceeds": t.exit_proceeds, "pnl": t.pnl, "pnl_pct": t.pnl_pct,
            "holding_days": t.holding_days, "exit_reason": t.exit_reason,
            "sector": t.sector,
        } for t in completed_trades])

        benchmark = None
        if not ihsg_df.empty:
            bench = ihsg_df["close"].reindex(equity_curve.index, method="ffill")
            if not bench.empty:
                benchmark = bench / bench.iloc[0] * initial_capital

        metrics = compute_all_metrics(
            equity_curve, trade_log, benchmark,
            risk_free_rate=self.config.backtest.risk_free_rate,
        )

        logger.info("\n" + format_metrics_report(metrics))

        return equity_curve, trade_log, metrics
