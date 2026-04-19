"""
Backtesting Engine v4 — Breakout + Foreign Flow
=================================================
Event-driven backtester using the new breakout signal engine.
"""

import logging
import math
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
    # Entry-time signal features (for post-trade analysis)
    composite_score: float = float("nan")
    breakout_strength: float = float("nan")
    vol_ratio: float = float("nan")
    rsi: float = float("nan")
    atr_pct: float = float("nan")
    price_vs_ma200: float = float("nan")
    prior_return_5d: float = float("nan")
    accumulation_score: float = float("nan")
    top_broker_acc: float = float("nan")
    net_foreign: float = float("nan")
    ff_confirmed: float = float("nan")
    entry_regime: str = ""
    ksei_net_5d: float = float("nan")
    dist_from_52w_high: float = float("nan")
    entry_exposure_mult: float = float("nan")


class BacktestEngine:

    def __init__(self, config: FrameworkConfig = DEFAULT_CONFIG):
        self.config = config
        self.signal_combiner = SignalCombiner(config)
        self.portfolio_mgr = PortfolioManager(config.sizing, config.exit)

    def run(self, universe_prices, ihsg_df, foreign_flows=None,
            broker_data=None, stock_sectors=None, fp_ratios=None):

        foreign_flows = foreign_flows or {}
        broker_data = broker_data or {}
        stock_sectors = stock_sectors or {}
        fp_ratios = fp_ratios or {}

        initial_capital = self.config.backtest.initial_capital
        start_date = pd.Timestamp(self.config.backtest.start_date)
        end_date = pd.Timestamp(self.config.backtest.end_date)

        # Pre-compute signals for all stocks
        logger.info("Pre-computing signals for all stocks...")
        all_signals = self.signal_combiner.generate_signals_universe(
            universe_prices, ihsg_df, foreign_flows, broker_data, fp_ratios=fp_ratios,
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
        cooldown_until: Dict[str, object] = {}
        recent_entry_dates: List[object] = []  # rolling window for cluster limit
        consecutive_losses: int = 0
        circuit_breaker_skip: int = 0  # signal days to skip

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
            if pending_entries:
                sorted_entries = sorted(pending_entries.items(), key=lambda x: x[1], reverse=True)
                max_entries = self.config.exit.max_entries_per_day
                entries_today = 0

                # Rolling 10-day cluster limit: prevent overtrading during fake breakout weeks
                # If >= max_entries_per_week entries were made in the last 10 trading days, pause
                lookback = 10
                recent_cutoff_idx = max(0, i - lookback)
                recent_cutoff_date = trading_dates[recent_cutoff_idx]
                recent_count = sum(1 for d in recent_entry_dates if d >= recent_cutoff_date)
                max_week = self.config.entry.max_entries_per_week
                if recent_count >= max_week:
                    pending_entries.clear()
                    continue

                for ticker, signal_score in sorted_entries:
                    if entries_today >= max_entries:
                        break

                    # Cooldown check
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

                        # Entry-day breakout_strength filter (Step 11):
                        # Applied at T+1 open (not signal day T) — on signal day breakout_strength
                        # is always >0 by definition, so the filter must run here at execution.
                        # Safe threshold -8%: blocks extreme overnight gap-downs only.
                        ef = self.config.entry_filter
                        if ef.use_breakout_strength_filter and sig_df is not None and current_date in sig_df.index:
                            bs = sig_df.loc[current_date].get("breakout_strength", float("nan"))
                            if not math.isnan(bs) and bs < ef.min_breakout_strength:
                                continue

                        # Combined BS/TBA filter (Step 11):
                        # Block when breakout faded (BS<0) AND big money selling (TBA<0).
                        # BS-/TBA- quadrant: 0 big winners across 2024+2025.
                        # No-op in CI: top_broker_acc defaults to 0 → tba<0 never fires.
                        if ef.use_combined_bs_tba_filter and sig_df is not None and current_date in sig_df.index:
                            sig_row = sig_df.loc[current_date]
                            bs = sig_row.get("breakout_strength", float("nan"))
                            tba = sig_row.get("top_broker_acc", 0)
                            if not math.isnan(bs) and bs < 0 and tba < 0:
                                continue

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

                        # Capture entry-time signal features for post-trade analysis
                        _SIGNAL_FEATURES = [
                            "composite_score", "breakout_strength", "vol_ratio", "rsi",
                            "atr_pct", "price_vs_ma200", "prior_return_5d",
                            "accumulation_score", "top_broker_acc", "net_foreign",
                            "ff_confirmed", "ksei_net_5d", "dist_from_52w_high", "fp_ratio",
                        ]
                        entry_signal_features = {"entry_regime": regime, "entry_exposure_mult": exposure_mult}
                        if sig_df is not None and current_date in sig_df.index:
                            sig_row = sig_df.loc[current_date]
                            for _f in _SIGNAL_FEATURES:
                                entry_signal_features[_f] = sig_row.get(_f, float("nan"))

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
                                    entry_signal_features=entry_signal_features,
                                )
                                portfolio.positions[ticker] = pos
                                portfolio.cash -= buy["total_cost"]
                                entries_today += 1
                                recent_entry_dates.append(current_date)

                pending_entries.clear()

            # ── 2. Check exits ──
            trades_before_exits = len(completed_trades)
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

                    _feats = pos.entry_signal_features
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
                        entry_signal_score=_feats.get("composite_score", 0.0),
                        composite_score=_feats.get("composite_score", float("nan")),
                        breakout_strength=_feats.get("breakout_strength", float("nan")),
                        vol_ratio=_feats.get("vol_ratio", float("nan")),
                        rsi=_feats.get("rsi", float("nan")),
                        atr_pct=_feats.get("atr_pct", float("nan")),
                        price_vs_ma200=_feats.get("price_vs_ma200", float("nan")),
                        prior_return_5d=_feats.get("prior_return_5d", float("nan")),
                        accumulation_score=_feats.get("accumulation_score", float("nan")),
                        top_broker_acc=_feats.get("top_broker_acc", float("nan")),
                        net_foreign=_feats.get("net_foreign", float("nan")),
                        ff_confirmed=_feats.get("ff_confirmed", float("nan")),
                        entry_regime=_feats.get("entry_regime", ""),
                        ksei_net_5d=_feats.get("ksei_net_5d", float("nan")),
                        dist_from_52w_high=_feats.get("dist_from_52w_high", float("nan")),
                        entry_exposure_mult=_feats.get("entry_exposure_mult", float("nan")),
                    )
                    completed_trades.append(trade)

                    # Cooldown after stop-loss
                    if exit_reason == "STOP_LOSS":
                        cooldown_days = self.config.exit.stop_loss_cooldown_days
                        future_idx = min(i + cooldown_days, len(trading_dates) - 1)
                        cooldown_until[ticker] = trading_dates[future_idx]

                    if pos.remaining_shares <= 0:
                        tickers_to_exit.append(ticker)

            for t in tickers_to_exit:
                del portfolio.positions[t]

            # ── 2b. Circuit breaker: track consecutive losses ──
            cb_threshold = self.config.entry.circuit_breaker_losses
            if cb_threshold > 0:
                for trade in completed_trades[trades_before_exits:]:
                    if trade.exit_reason == "PARTIAL_PROFIT":
                        continue
                    if trade.pnl < 0:
                        consecutive_losses += 1
                        if consecutive_losses >= cb_threshold:
                            circuit_breaker_skip = self.config.entry.circuit_breaker_pause
                            consecutive_losses = 0
                            logger.info(f"{current_date.date() if hasattr(current_date, 'date') else current_date}: "
                                        f"Circuit breaker triggered — pausing entries for "
                                        f"{self.config.entry.circuit_breaker_pause} signal days")
                    else:
                        consecutive_losses = 0

            # ── 3. Generate entry signals ──
            if circuit_breaker_skip > 0:
                circuit_breaker_skip -= 1
            else:
                for ticker, sig_df in all_signals.items():
                    if sig_df is None or sig_df.empty:
                        continue
                    if current_date not in sig_df.index:
                        continue

                    sig_row = sig_df.loc[current_date]

                    # Pyramiding (Step 12): if already held and in trend mode,
                    # add to the position on a new breakout signal.
                    pcfg = self.config.pyramid
                    if ticker in portfolio.positions and pcfg.enable_pyramiding:
                        pos = portfolio.positions[ticker]
                        if (pos.in_trend_mode
                                and pos.pyramid_count < pcfg.max_adds
                                and sig_row.get("is_breakout", False)):
                            # Execute pyramid add immediately (same-day signal → same-day add)
                            add_open = current_data.get(ticker, {}).get("open",
                                current_data.get(ticker, {}).get("close", 0))
                            if add_open > 0:
                                add_atr = sig_row.get("atr", pos.entry_atr) or pos.entry_atr
                                # Size = fraction of original initial allocation
                                add_shares = round_to_lot(
                                    int(pos.shares * pcfg.add_size_fraction)
                                )
                                if add_shares >= 100:
                                    add_buy = compute_buy_cost(add_open, add_shares)
                                    if add_buy["total_cost"] <= portfolio.cash:
                                        portfolio.cash -= add_buy["total_cost"]
                                        pos.remaining_shares += add_shares
                                        pos.shares += add_shares
                                        pos.total_cost += add_buy["total_cost"]
                                        pos.pyramid_count += 1
                                        pos.pyramid_shares += add_shares
                                        pos.pyramid_cost += add_buy["total_cost"]
                                        # Raise stop to protect new capital
                                        new_stop = add_buy["exec_price"] * (
                                            1 - self.config.exit.stop_loss_pct
                                        )
                                        pos.stop_price = max(pos.stop_price, new_stop)
                                        logger.info(
                                            f"PYRAMID add: {ticker} x{add_shares} "
                                            f"@ {add_open:.0f} (add #{pos.pyramid_count}), "
                                            f"stop raised to {pos.stop_price:.0f}"
                                        )
                        continue  # don't add to pending_entries for held tickers

                    if ticker in portfolio.positions:
                        continue

                    if sig_row.get("signal") == "BUY":
                        pending_entries[ticker] = sig_row.get("composite_score", 0.0)

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
            # Entry-time signal features
            "composite_score": t.composite_score,
            "breakout_strength": t.breakout_strength,
            "vol_ratio": t.vol_ratio,
            "rsi": t.rsi,
            "atr_pct": t.atr_pct,
            "price_vs_ma200": t.price_vs_ma200,
            "prior_return_5d": t.prior_return_5d,
            "accumulation_score": t.accumulation_score,
            "top_broker_acc": t.top_broker_acc,
            "net_foreign": t.net_foreign,
            "ff_confirmed": t.ff_confirmed,
            "entry_regime": t.entry_regime,
            "ksei_net_5d": t.ksei_net_5d,
            "dist_from_52w_high": t.dist_from_52w_high,
            "entry_exposure_mult": t.entry_exposure_mult,
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
