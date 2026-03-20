"""
Performance Metrics Calculator
================================
Computes all backtesting performance metrics.
"""

import logging
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def compute_all_metrics(
    equity_curve: pd.Series,
    trade_log: pd.DataFrame,
    benchmark_curve: Optional[pd.Series] = None,
    risk_free_rate: float = 0.06,
    trading_days_per_year: int = 245,
) -> Dict:
    """
    Compute comprehensive performance metrics.

    Args:
        equity_curve: Series of daily portfolio equity values (DatetimeIndex)
        trade_log: DataFrame with columns including pnl, holding_days, etc.
        benchmark_curve: Optional Series of benchmark (IHSG) values
        risk_free_rate: Annualised risk-free rate (BI rate)
        trading_days_per_year: ~245 for IDX

    Returns:
        Dict of all metrics.
    """
    metrics = {}

    if equity_curve.empty:
        return {"error": "Empty equity curve"}

    # ── Returns ──
    total_days = len(equity_curve)
    years = total_days / trading_days_per_year

    initial = equity_curve.iloc[0]
    final = equity_curve.iloc[-1]

    metrics["initial_capital"] = initial
    metrics["final_equity"] = final
    metrics["total_return_pct"] = (final / initial - 1) * 100
    metrics["cagr_pct"] = ((final / initial) ** (1 / max(years, 0.01)) - 1) * 100 if years > 0 else 0

    # ── Daily returns ──
    daily_returns = equity_curve.pct_change().dropna()

    metrics["avg_daily_return_pct"] = daily_returns.mean() * 100
    metrics["daily_volatility_pct"] = daily_returns.std() * 100
    metrics["annualised_volatility_pct"] = daily_returns.std() * np.sqrt(trading_days_per_year) * 100

    # ── Sharpe Ratio ──
    daily_rf = (1 + risk_free_rate) ** (1 / trading_days_per_year) - 1
    excess_returns = daily_returns - daily_rf
    if excess_returns.std() > 0:
        metrics["sharpe_ratio"] = (
            excess_returns.mean() / excess_returns.std()
        ) * np.sqrt(trading_days_per_year)
    else:
        metrics["sharpe_ratio"] = 0.0

    # ── Sortino Ratio ──
    downside_returns = excess_returns[excess_returns < 0]
    if len(downside_returns) > 0 and downside_returns.std() > 0:
        metrics["sortino_ratio"] = (
            excess_returns.mean() / downside_returns.std()
        ) * np.sqrt(trading_days_per_year)
    else:
        metrics["sortino_ratio"] = 0.0

    # ── Drawdown Analysis ──
    cummax = equity_curve.cummax()
    drawdown = (equity_curve - cummax) / cummax
    metrics["max_drawdown_pct"] = drawdown.min() * 100

    # Calmar ratio = CAGR / |max drawdown|
    if metrics["max_drawdown_pct"] != 0:
        metrics["calmar_ratio"] = metrics["cagr_pct"] / abs(metrics["max_drawdown_pct"])
    else:
        metrics["calmar_ratio"] = 0.0

    # Drawdown duration
    in_drawdown = drawdown < 0
    dd_groups = (~in_drawdown).cumsum()
    if in_drawdown.any():
        dd_lengths = in_drawdown.groupby(dd_groups).sum()
        metrics["max_drawdown_days"] = int(dd_lengths.max())
    else:
        metrics["max_drawdown_days"] = 0

    # ── Trade Statistics ──
    if not trade_log.empty and "pnl" in trade_log.columns:
        trades = trade_log.copy()
        metrics["total_trades"] = len(trades)

        winners = trades[trades["pnl"] > 0]
        losers = trades[trades["pnl"] <= 0]

        metrics["winning_trades"] = len(winners)
        metrics["losing_trades"] = len(losers)
        metrics["win_rate_pct"] = (
            len(winners) / len(trades) * 100 if len(trades) > 0 else 0
        )

        metrics["avg_win"] = winners["pnl"].mean() if len(winners) > 0 else 0
        metrics["avg_loss"] = losers["pnl"].mean() if len(losers) > 0 else 0

        # Profit factor = gross wins / gross losses
        gross_wins = winners["pnl"].sum() if len(winners) > 0 else 0
        gross_losses = abs(losers["pnl"].sum()) if len(losers) > 0 else 1
        metrics["profit_factor"] = gross_wins / gross_losses if gross_losses > 0 else float("inf")

        # Average holding period
        if "holding_days" in trades.columns:
            metrics["avg_holding_days"] = trades["holding_days"].mean()
        else:
            metrics["avg_holding_days"] = 0

        # Maximum consecutive losses
        if len(trades) > 0:
            is_loss = (trades["pnl"] <= 0).astype(int)
            groups = (is_loss != is_loss.shift()).cumsum()
            consec = is_loss.groupby(groups).sum()
            metrics["max_consecutive_losses"] = int(consec.max()) if len(consec) > 0 else 0
        else:
            metrics["max_consecutive_losses"] = 0

        # Average PnL per trade
        metrics["avg_pnl_per_trade"] = trades["pnl"].mean()
        metrics["total_pnl"] = trades["pnl"].sum()
    else:
        metrics["total_trades"] = 0
        metrics["win_rate_pct"] = 0

    # ── Exposure Time ──
    # Fraction of days when portfolio was invested (had positions)
    if "invested" in equity_curve.index.names or hasattr(equity_curve, "invested"):
        pass  # would need separate tracking
    # Approximate: days where equity changed (was invested)
    invested_days = (daily_returns != 0).sum()
    metrics["exposure_pct"] = invested_days / max(total_days, 1) * 100

    # ── Benchmark Comparison ──
    if benchmark_curve is not None and not benchmark_curve.empty:
        bench_start = benchmark_curve.iloc[0]
        bench_end = benchmark_curve.iloc[-1]
        bench_return = (bench_end / bench_start - 1) * 100
        bench_cagr = ((bench_end / bench_start) ** (1 / max(years, 0.01)) - 1) * 100

        metrics["benchmark_return_pct"] = bench_return
        metrics["benchmark_cagr_pct"] = bench_cagr
        metrics["alpha_pct"] = metrics["cagr_pct"] - bench_cagr

        # Benchmark drawdown
        bench_cummax = benchmark_curve.cummax()
        bench_dd = (benchmark_curve - bench_cummax) / bench_cummax
        metrics["benchmark_max_drawdown_pct"] = bench_dd.min() * 100
    else:
        metrics["benchmark_return_pct"] = None
        metrics["alpha_pct"] = None

    # ── Monthly Returns ──
    if len(daily_returns) > 20:
        monthly = equity_curve.resample("ME").last()
        monthly_returns = monthly.pct_change().dropna()
        metrics["monthly_returns"] = monthly_returns
        metrics["best_month_pct"] = monthly_returns.max() * 100
        metrics["worst_month_pct"] = monthly_returns.min() * 100
    else:
        metrics["monthly_returns"] = pd.Series(dtype=float)

    # ── Yearly Returns ──
    if len(daily_returns) > 200:
        yearly = equity_curve.resample("YE").last()
        yearly_returns = yearly.pct_change().dropna()
        metrics["yearly_returns"] = yearly_returns
    else:
        metrics["yearly_returns"] = pd.Series(dtype=float)

    return metrics


def format_metrics_report(metrics: Dict) -> str:
    """Format metrics into a human-readable report string."""
    lines = [
        "=" * 60,
        "  IDX SWING TRADING FRAMEWORK — BACKTEST RESULTS",
        "=" * 60,
        "",
        "── RETURNS ──",
        f"  Initial Capital:        Rp {metrics.get('initial_capital', 0):>20,.0f}",
        f"  Final Equity:           Rp {metrics.get('final_equity', 0):>20,.0f}",
        f"  Total Return:           {metrics.get('total_return_pct', 0):>10.2f} %",
        f"  CAGR:                   {metrics.get('cagr_pct', 0):>10.2f} %",
        "",
        "── RISK ──",
        f"  Max Drawdown:           {metrics.get('max_drawdown_pct', 0):>10.2f} %",
        f"  Max DD Duration:        {metrics.get('max_drawdown_days', 0):>10d} days",
        f"  Annual Volatility:      {metrics.get('annualised_volatility_pct', 0):>10.2f} %",
        "",
        "── RISK-ADJUSTED ──",
        f"  Sharpe Ratio:           {metrics.get('sharpe_ratio', 0):>10.2f}",
        f"  Sortino Ratio:          {metrics.get('sortino_ratio', 0):>10.2f}",
        f"  Calmar Ratio:           {metrics.get('calmar_ratio', 0):>10.2f}",
        "",
        "── TRADES ──",
        f"  Total Trades:           {metrics.get('total_trades', 0):>10d}",
        f"  Win Rate:               {metrics.get('win_rate_pct', 0):>10.1f} %",
        f"  Profit Factor:          {metrics.get('profit_factor', 0):>10.2f}",
        f"  Avg Win:                Rp {metrics.get('avg_win', 0):>15,.0f}",
        f"  Avg Loss:               Rp {metrics.get('avg_loss', 0):>15,.0f}",
        f"  Avg Holding Period:     {metrics.get('avg_holding_days', 0):>10.1f} days",
        f"  Max Consecutive Losses: {metrics.get('max_consecutive_losses', 0):>10d}",
        f"  Exposure:               {metrics.get('exposure_pct', 0):>10.1f} %",
        "",
    ]

    if metrics.get("benchmark_return_pct") is not None:
        lines.extend([
            "── BENCHMARK (IHSG) ──",
            f"  Benchmark Return:       {metrics['benchmark_return_pct']:>10.2f} %",
            f"  Benchmark CAGR:         {metrics.get('benchmark_cagr_pct', 0):>10.2f} %",
            f"  Alpha:                  {metrics.get('alpha_pct', 0):>10.2f} %",
            f"  Benchmark Max DD:       {metrics.get('benchmark_max_drawdown_pct', 0):>10.2f} %",
            "",
        ])

    lines.extend([
        "=" * 60,
        "  DISCLAIMER: Past performance does not guarantee future results.",
        "  This is for educational/research purposes only.",
        "=" * 60,
    ])

    return "\n".join(lines)
