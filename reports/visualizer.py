"""
Report Visualizer
==================
Generates charts for backtest results:
  - Equity curve (strategy vs benchmark)
  - Drawdown chart
  - Monthly returns heatmap
  - Trade distribution charts
"""

import logging
from pathlib import Path
from typing import Dict, Optional

import numpy as np
import pandas as pd

try:
    import matplotlib
    matplotlib.use("Agg")  # non-interactive backend
    import matplotlib.pyplot as plt
    import matplotlib.ticker as mticker
    from matplotlib.colors import LinearSegmentedColormap
except ImportError:
    raise ImportError("Install matplotlib: pip install matplotlib")

logger = logging.getLogger(__name__)

COLORS = {
    "equity": "#1565C0",
    "benchmark": "#9E9E9E",
    "drawdown": "#D32F2F",
    "positive": "#2E7D32",
    "negative": "#C62828",
    "neutral": "#F5F5F5",
    "grid": "#E0E0E0",
}


def plot_equity_curve(
    equity_curve: pd.Series,
    benchmark_curve: Optional[pd.Series] = None,
    title: str = "IDX Swing Trader — Equity Curve",
    output_path: str = "reports/equity_curve.png",
):
    fig, ax = plt.subplots(figsize=(14, 6))
    ax.plot(equity_curve.index, equity_curve.values,
            color=COLORS["equity"], linewidth=1.5, label="Strategy")

    if benchmark_curve is not None and not benchmark_curve.empty:
        bench = benchmark_curve.reindex(equity_curve.index, method="ffill")
        ax.plot(bench.index, bench.values,
                color=COLORS["benchmark"], linewidth=1.2,
                linestyle="--", label="IHSG (Buy & Hold)")

    ax.set_title(title, fontsize=14, fontweight="bold")
    ax.set_ylabel("Portfolio Value (IDR)", fontsize=11)
    ax.legend(loc="upper left", fontsize=10)
    ax.grid(True, alpha=0.3, color=COLORS["grid"])
    ax.yaxis.set_major_formatter(
        mticker.FuncFormatter(lambda x, _: f"Rp {x/1e9:.1f}B")
    )
    fig.tight_layout()
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    logger.info(f"Equity curve saved: {output_path}")


def plot_drawdown(
    equity_curve: pd.Series,
    title: str = "Drawdown",
    output_path: str = "reports/drawdown.png",
):
    cummax = equity_curve.cummax()
    drawdown = (equity_curve - cummax) / cummax * 100

    fig, ax = plt.subplots(figsize=(14, 4))
    ax.fill_between(drawdown.index, drawdown.values, 0,
                    color=COLORS["drawdown"], alpha=0.4)
    ax.plot(drawdown.index, drawdown.values,
            color=COLORS["drawdown"], linewidth=0.8)

    ax.set_title(title, fontsize=14, fontweight="bold")
    ax.set_ylabel("Drawdown (%)", fontsize=11)
    ax.grid(True, alpha=0.3, color=COLORS["grid"])

    min_dd = drawdown.min()
    min_dd_date = drawdown.idxmin()
    ax.annotate(f"Max DD: {min_dd:.1f}%", xy=(min_dd_date, min_dd),
                xytext=(min_dd_date, min_dd - 3), fontsize=9,
                color=COLORS["drawdown"],
                arrowprops=dict(arrowstyle="->", color=COLORS["drawdown"]))

    fig.tight_layout()
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    logger.info(f"Drawdown chart saved: {output_path}")


def plot_monthly_heatmap(
    equity_curve: pd.Series,
    title: str = "Monthly Returns (%)",
    output_path: str = "reports/monthly_heatmap.png",
):
    monthly = equity_curve.resample("ME").last()
    monthly_returns = monthly.pct_change().dropna() * 100

    years = sorted(monthly_returns.index.year.unique())
    month_labels = ["Jan","Feb","Mar","Apr","May","Jun",
                    "Jul","Aug","Sep","Oct","Nov","Dec"]

    data = np.full((len(years), 12), np.nan)
    for dt, val in monthly_returns.items():
        y_idx = years.index(dt.year)
        m_idx = dt.month - 1
        data[y_idx, m_idx] = val

    fig, ax = plt.subplots(figsize=(14, max(3, len(years) * 0.8)))
    cmap = LinearSegmentedColormap.from_list(
        "returns", [COLORS["negative"], "#FFFFFF", COLORS["positive"]])

    vmax = np.nanmax(np.abs(data)) if not np.all(np.isnan(data)) else 10
    vmax = max(vmax, 5)

    im = ax.imshow(data, cmap=cmap, aspect="auto", vmin=-vmax, vmax=vmax)
    ax.set_xticks(range(12))
    ax.set_xticklabels(month_labels, fontsize=10)
    ax.set_yticks(range(len(years)))
    ax.set_yticklabels([str(y) for y in years], fontsize=10)
    ax.set_title(title, fontsize=14, fontweight="bold", pad=15)

    for i in range(len(years)):
        for j in range(12):
            val = data[i, j]
            if not np.isnan(val):
                color = "white" if abs(val) > vmax * 0.6 else "black"
                ax.text(j, i, f"{val:.1f}", ha="center", va="center",
                        fontsize=9, color=color, fontweight="bold")

    cbar = fig.colorbar(im, ax=ax, shrink=0.8, pad=0.02)
    cbar.set_label("Return (%)", fontsize=10)
    fig.tight_layout()
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    logger.info(f"Monthly heatmap saved: {output_path}")


def plot_trade_distribution(
    trade_log: pd.DataFrame,
    title: str = "Trade PnL Distribution",
    output_path: str = "reports/trade_distribution.png",
):
    if trade_log.empty or "pnl_pct" not in trade_log.columns:
        return

    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    ax1 = axes[0]
    pnl_pct = trade_log["pnl_pct"]
    ax1.hist(pnl_pct, bins=30, color=COLORS["equity"], alpha=0.7, edgecolor="white")
    ax1.axvline(0, color="black", linewidth=0.8, linestyle="--")
    ax1.axvline(pnl_pct.mean(), color=COLORS["positive"], linewidth=1.5,
                label=f"Mean: {pnl_pct.mean():.1f}%")
    ax1.set_title("Trade Returns Distribution", fontsize=12, fontweight="bold")
    ax1.set_xlabel("PnL (%)")
    ax1.set_ylabel("Count")
    ax1.legend()
    ax1.grid(True, alpha=0.3)

    ax2 = axes[1]
    if "exit_reason" in trade_log.columns:
        reason_counts = trade_log["exit_reason"].value_counts()
        reason_colors = {
            "STOP_LOSS": COLORS["negative"], "PARTIAL_PROFIT": COLORS["positive"],
            "TIME_EXIT": "#FFA726", "BIG_MONEY_EXIT": "#7B1FA2",
            "REGIME_EXIT": "#455A64", "TRAILING_STOP": "#1565C0",
        }
        bar_colors = [reason_colors.get(r, "#9E9E9E") for r in reason_counts.index]
        ax2.barh(reason_counts.index, reason_counts.values, color=bar_colors)
        ax2.set_title("Exit Reasons", fontsize=12, fontweight="bold")
        ax2.set_xlabel("Count")
        ax2.grid(True, alpha=0.3, axis="x")

    fig.tight_layout()
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    logger.info(f"Trade distribution saved: {output_path}")


def generate_all_reports(
    equity_curve: pd.Series,
    trade_log: pd.DataFrame,
    metrics: Dict,
    benchmark_curve: Optional[pd.Series] = None,
    output_dir: str = "reports",
):
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    plot_equity_curve(equity_curve, benchmark_curve,
                      output_path=f"{output_dir}/equity_curve.png")
    plot_drawdown(equity_curve, output_path=f"{output_dir}/drawdown.png")

    if len(equity_curve) > 30:
        plot_monthly_heatmap(equity_curve,
                             output_path=f"{output_dir}/monthly_heatmap.png")

    if not trade_log.empty:
        plot_trade_distribution(trade_log,
                                output_path=f"{output_dir}/trade_distribution.png")
        csv_path = f"{output_dir}/trade_log.csv"
        trade_log.to_csv(csv_path, index=False)
        logger.info(f"Trade log saved: {csv_path}")

    from backtest.metrics import format_metrics_report
    report_text = format_metrics_report(metrics)
    report_path = f"{output_dir}/metrics_summary.txt"
    with open(report_path, "w") as f:
        f.write(report_text)
    logger.info(f"Metrics summary saved: {report_path}")
    logger.info(f"All reports generated in {output_dir}/")
