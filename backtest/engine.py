"""
Backtesting Engine
===================
Event-driven backtester that simulates the trading framework
against historical IDX data.

Walk-forward methodology:
  - Process one trading day at a time
  - Signals are computed using only data available up to that day
  - No look-ahead bias

Execution assumptions:
  - Entry at next day's open (after signal generated at close)
  - Exit at the trigger price or next open (whichever applies)
"""

import logging
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from config import FrameworkConfig, DEFAULT_CONFIG
from backtest.portfolio import (
    PortfolioManager, PortfolioState, Position,
)
from backtest.costs import (
    compute_buy_cost, compute_sell_proceeds, round_to_lot,
)
from backtest.metrics import compute_all_metrics, format_metrics_report
from signals.signal_combiner import SignalCombiner

logger = logging.getLogger(__name__)


@dataclass
class Trade:
    """Completed trade record."""
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
    """
    Event-driven backtesting engine for the IDX swing trading framework.

    Processes one day at a time:
      1. Update portfolio with current prices
      2. Check exit conditions for all open positions
      3. Execute exits
      4. Check for new entry signals
      5. Execute entries (within risk limits)
      6. Record equity curve
    """

    def __init__(self, config: FrameworkConfig = DEFAULT_CONFIG):
        self.config = config
        self.signal_combiner = SignalCombiner(config)
        self.portfolio_mgr = PortfolioManager(config.sizing, config.exit)

    def run(
        self,
        universe_prices: Dict[str, pd.DataFrame],
        ihsg_df: pd.DataFrame,
        foreign_flows: Optional[Dict[str, pd.DataFrame]] = None,
        broker_data: Optional[Dict[str, pd.DataFrame]] = None,
        stock_sectors: Optional[Dict[str, str]] = None,
    ) -> Tuple[pd.Series, pd.DataFrame, Dict]:
        """
        Run the full backtest.

        Args:
            universe_prices: dict of ticker → OHLCV DataFrame (DatetimeIndex)
            ihsg_df: IHSG DataFrame (DatetimeIndex)
            foreign_flows: optional dict of ticker → foreign flow DataFrame
            broker_data: optional dict of ticker → broker summary DataFrame
            stock_sectors: optional dict of ticker → sector string

        Returns:
            (equity_curve, trade_log_df, metrics_dict)
        """
        foreign_flows = foreign_flows or {}
        broker_data = broker_data or {}
        stock_sectors = stock_sectors or {}

        initial_capital = self.config.backtest.initial_capital
        start_date = pd.Timestamp(self.config.backtest.start_date)
        end_date = pd.Timestamp(self.config.backtest.end_date)

        # ── Pre-compute signals for all stocks ──
        logger.info("Pre-computing signals for all stocks...")
        all_signals = self.signal_combiner.generate_signals_universe(
            universe_prices, ihsg_df, foreign_flows, broker_data,
        )

        # ── Build a unified calendar of trading dates ──
        all_dates = set()
        for df in universe_prices.values():
            if not df.empty:
                all_dates.update(df.index)
        if not ihsg_df.empty:
            all_dates.update(ihsg_df.index)

        trading_dates = sorted([
            d for d in all_dates
            if start_date <= d <= end_date
        ])

        if not trading_dates:
            logger.error("No trading dates in the specified range")
            return pd.Series(dtype=float), pd.DataFrame(), {}

        logger.info(
            f"Backtesting {len(trading_dates)} trading days "
            f"from {trading_dates[0]} to {trading_dates[-1]}"
        )

        # ── Initialise portfolio ──
        portfolio = PortfolioState(cash=initial_capital, total_equity=initial_capital)

        # ── Main loop ──
        equity_history = {}
        completed_trades: List[Trade] = []
        pending_entries: Dict[str, float] = {}  # ticker → signal score (for next day entry)

        # FIX 3: Track cooldown — ticker → date when cooldown expires
        cooldown_until: Dict[str, object] = {}

        # Fix A: Track consecutive signal days per ticker
        # ticker → count of consecutive days with BUY signal
        consecutive_signal_days: Dict[str, int] = {}

        for i, current_date in enumerate(trading_dates):
            # Gather current prices
            current_prices = {}
            current_data = {}
            for ticker, df in universe_prices.items():
                if current_date in df.index:
                    row = df.loc[current_date]
                    current_prices[ticker] = row["close"]
                    current_data[ticker] = row

            # Update equity
            portfolio.update_equity(current_prices)

            # ── 1. Execute pending entries (from yesterday's signals) ──
            if pending_entries:
                # FIX 5: Sort by score descending and limit entries per day
                sorted_entries = sorted(
                    pending_entries.items(), key=lambda x: x[1], reverse=True
                )
                max_entries = self.config.exit.max_entries_per_day
                entries_today = 0

                for ticker, signal_score in sorted_entries:
                    if entries_today >= max_entries:
                        break

                    # FIX 3: Check cooldown
                    if ticker in cooldown_until and current_date < cooldown_until[ticker]:
                        continue

                    if ticker in current_data and ticker not in portfolio.positions:
                        row = current_data[ticker]
                        open_price = row.get("open", row["close"])

                        # Fix C: Skip if open gaps down > 2% from prior close
                        # This means something changed overnight — signal is stale
                        if i > 0:
                            prev_date = trading_dates[i - 1]
                            prev_close = current_prices.get(ticker)
                            # Get yesterday's close from the price df
                            ticker_df = universe_prices.get(ticker)
                            if ticker_df is not None and prev_date in ticker_df.index:
                                prev_close = ticker_df.loc[prev_date]["close"]
                                if prev_close > 0:
                                    gap_pct = (open_price - prev_close) / prev_close
                                    if gap_pct < -self.config.entry.max_gap_down_pct:
                                        logger.debug(
                                            f"  SKIP {ticker}: gap down {gap_pct:.1%} "
                                            f"at open (limit: -{self.config.entry.max_gap_down_pct:.0%})"
                                        )
                                        continue

                        sig_df = all_signals.get(ticker)
                        atr = 0.0
                        if sig_df is not None and current_date in sig_df.index:
                            atr = sig_df.loc[current_date].get("atr", 0)
                        if atr <= 0:
                            atr = open_price * 0.03  # fallback: 3% of price

                        # Get regime exposure
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
                                logger.debug(
                                    f"  BUY {ticker}: {shares} shares @ "
                                    f"{buy['exec_price']:.0f}, "
                                    f"stop={stop:.0f}, cost={buy['total_cost']:,.0f}"
                                )

                pending_entries.clear()

            # ── 2. Check exits for open positions ──
            tickers_to_exit = []
            for ticker, pos in list(portfolio.positions.items()):
                if ticker not in current_data:
                    continue

                row = current_data[ticker]
                sig_df = all_signals.get(ticker)

                # Get current indicators
                composite_score = 0.5
                regime = "SIDEWAYS"
                atr = pos.entry_atr
                if sig_df is not None and current_date in sig_df.index:
                    sig_row = sig_df.loc[current_date]
                    composite_score = sig_row.get("composite_score", 0.5)
                    regime = sig_row.get("regime", "SIDEWAYS")
                    atr = sig_row.get("atr", atr)

                # Update trailing stop
                self.portfolio_mgr.update_trailing_stop(pos, row["close"], atr)

                # Increment days held
                pos.days_held += 1

                # Check exit conditions
                exit_reason, fraction = self.portfolio_mgr.check_exit_conditions(
                    pos, row["close"], row["low"], atr,
                    composite_score, regime, pos.days_held,
                )

                if exit_reason and fraction > 0:
                    shares_to_sell = round_to_lot(
                        int(pos.remaining_shares * fraction)
                    )
                    if shares_to_sell < 100:
                        shares_to_sell = pos.remaining_shares  # sell all if less than 1 lot

                    # Use stop price or close for exit price
                    if exit_reason == "STOP_LOSS":
                        exit_price = pos.stop_price  # assume stop was hit
                    else:
                        exit_price = row["close"]

                    sell = compute_sell_proceeds(exit_price, shares_to_sell)
                    portfolio.cash += sell["net_proceeds"]
                    pos.remaining_shares -= shares_to_sell

                    # Record trade
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

                    # FIX 3: Set cooldown after stop-loss
                    if exit_reason == "STOP_LOSS":
                        cooldown_days = self.config.exit.stop_loss_cooldown_days
                        # Find the date N trading days from now
                        future_idx = min(i + cooldown_days, len(trading_dates) - 1)
                        cooldown_until[ticker] = trading_dates[future_idx]

                    logger.debug(
                        f"  EXIT {ticker}: {shares_to_sell} shares @ "
                        f"{sell['exec_price']:.0f}, "
                        f"PnL={pnl:+,.0f} ({trade.pnl_pct:+.1f}%), "
                        f"reason={exit_reason}"
                    )

                    if pos.remaining_shares <= 0:
                        tickers_to_exit.append(ticker)

            # Remove fully closed positions
            for t in tickers_to_exit:
                del portfolio.positions[t]

            # ── 3. Generate entry signals for tomorrow ──
            # Fix A: Track consecutive signal days — only enter after N consecutive BUY signals
            required_days = self.config.entry.signal_confirmation_days
            tickers_with_signal_today = set()

            for ticker, sig_df in all_signals.items():
                if ticker in portfolio.positions:
                    continue  # already in position
                if sig_df is None or sig_df.empty:
                    continue
                if current_date not in sig_df.index:
                    continue

                sig_row = sig_df.loc[current_date]
                if sig_row.get("signal") == "BUY":
                    tickers_with_signal_today.add(ticker)
                    # Increment consecutive day counter
                    consecutive_signal_days[ticker] = consecutive_signal_days.get(ticker, 0) + 1

                    # Only promote to pending entry if signal persisted N days
                    if consecutive_signal_days[ticker] >= required_days:
                        pending_entries[ticker] = sig_row.get("composite_score", 0)

            # Reset counter for tickers that lost their BUY signal today
            for ticker in list(consecutive_signal_days.keys()):
                if ticker not in tickers_with_signal_today:
                    consecutive_signal_days[ticker] = 0

            # ── 4. Record equity ──
            portfolio.update_equity(current_prices)
            equity_history[current_date] = portfolio.total_equity

        # ── Build results ──
        equity_curve = pd.Series(equity_history, name="equity")
        equity_curve.index = pd.DatetimeIndex(equity_curve.index)

        trade_log = pd.DataFrame([{
            "ticker": t.ticker,
            "entry_date": t.entry_date,
            "exit_date": t.exit_date,
            "entry_price": t.entry_price,
            "exit_price": t.exit_price,
            "shares": t.shares,
            "entry_cost": t.entry_cost,
            "exit_proceeds": t.exit_proceeds,
            "pnl": t.pnl,
            "pnl_pct": t.pnl_pct,
            "holding_days": t.holding_days,
            "exit_reason": t.exit_reason,
            "sector": t.sector,
        } for t in completed_trades])

        # Benchmark curve
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
