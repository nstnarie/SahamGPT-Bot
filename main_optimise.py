#!/usr/bin/env python3
"""
Walk-Forward Optimisation Engine
==================================

Properly backtests and tunes the framework parameters WITHOUT overfitting.

The problem with naive backtesting:
  If you optimise parameters on 2021–2024 data and then evaluate on
  the SAME 2021–2024 data, you're guaranteed to overfit. The strategy
  will look amazing in backtest but fail in live trading.

Walk-forward methodology:
  1. Split history into rolling windows:
     [Train: 2021-01 to 2022-06] → [Test: 2022-07 to 2022-12]
     [Train: 2021-07 to 2023-01] → [Test: 2023-01 to 2023-06]
     [Train: 2022-01 to 2023-06] → [Test: 2023-07 to 2023-12]
     [Train: 2022-07 to 2024-01] → [Test: 2024-01 to 2024-06]

  2. For each window: optimise on train, evaluate on test (unseen data)
  3. The REAL performance is the combined out-of-sample test results

This gives you an honest estimate of how the system would have performed
if you'd been tuning it in real time.

Usage:
    python main_optimise.py --start 2021-01-01 --end 2024-12-31
    python main_optimise.py --param-grid conservative
    python main_optimise.py --param-grid aggressive

DISCLAIMER: For educational and research purposes only.
"""

import argparse
import copy
import itertools
import json
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))

from config import FrameworkConfig, DATABASE_URL
from database.schema import create_all_tables, get_session, get_engine
from database.data_loader import (
    load_prices_as_dataframe, load_index_df, load_foreign_flow_df,
)
from scraper.price_scraper import LQ45_TICKERS
from backtest.engine import BacktestEngine
from backtest.metrics import compute_all_metrics, format_metrics_report

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────
# PARAMETER GRIDS
# ──────────────────────────────────────────────────────────────

# Each grid defines alternative values to test for key parameters.
# We keep the grid SMALL (< 50 combinations) to avoid data-mining bias.

PARAM_GRIDS = {
    "conservative": {
        # Big money thresholds
        "big_money.score_entry_threshold": [0.50, 0.55, 0.60],
        # Stop loss
        "exit.stop_loss_pct": [0.05, 0.07, 0.10],
        # Time exit
        "exit.time_exit_max_days": [15, 20, 30],
    },
    "aggressive": {
        "big_money.score_entry_threshold": [0.45, 0.50, 0.55],
        "big_money.weight_foreign_flow": [0.30, 0.35, 0.40],
        "big_money.weight_volume_price": [0.30, 0.35, 0.40],
        "exit.stop_loss_pct": [0.05, 0.07],
        "exit.trailing_activation_pct": [0.08, 0.10, 0.12],
        "exit.time_exit_max_days": [15, 20, 25],
    },
    "technical_focus": {
        "technical.rsi_min": [35, 40, 45],
        "technical.rsi_max": [65, 70, 75],
        "technical.entry_volume_multiplier": [1.0, 1.2, 1.5],
        "exit.stop_loss_pct": [0.05, 0.07, 0.10],
    },
    "minimal": {
        # Absolute minimum grid for quick validation
        "big_money.score_entry_threshold": [0.50, 0.60],
        "exit.stop_loss_pct": [0.05, 0.07],
    },
}


def apply_params_to_config(
    base_config: FrameworkConfig,
    params: Dict[str, float],
) -> FrameworkConfig:
    """
    Apply a parameter dict to a config, returning a new config.
    Param keys use dot notation: "big_money.score_entry_threshold"
    """
    cfg = copy.deepcopy(base_config)

    for key, value in params.items():
        parts = key.split(".")
        obj = cfg
        for part in parts[:-1]:
            obj = getattr(obj, part)
        setattr(obj, parts[-1], value)

    return cfg


def generate_param_combinations(grid: Dict[str, List]) -> List[Dict]:
    """
    Generate all combinations from a parameter grid.
    Filters out combinations where weights don't sum properly.
    """
    keys = list(grid.keys())
    values = list(grid.values())

    combos = []
    for combo in itertools.product(*values):
        params = dict(zip(keys, combo))

        # Validate: if we have weight params, ensure they're reasonable
        weight_keys = [k for k in params if "weight_" in k]
        if weight_keys:
            weight_sum = sum(params[k] for k in weight_keys)
            # Allow some slack (weights don't need to sum to 1.0 exactly
            # since the third weight is computed implicitly)
            if weight_sum > 1.05:
                continue

        combos.append(params)

    return combos


# ──────────────────────────────────────────────────────────────
# WALK-FORWARD WINDOWS
# ──────────────────────────────────────────────────────────────

def generate_walk_forward_windows(
    start_date: str,
    end_date: str,
    train_months: int = 18,
    test_months: int = 6,
    step_months: int = 6,
) -> List[Dict]:
    """
    Generate rolling train/test windows.

    Args:
        train_months: Length of training window
        test_months: Length of out-of-sample test window
        step_months: How far to advance between windows

    Returns:
        List of {"train_start", "train_end", "test_start", "test_end"}
    """
    start = pd.Timestamp(start_date)
    end = pd.Timestamp(end_date)

    windows = []
    current = start

    while True:
        train_start = current
        train_end = train_start + pd.DateOffset(months=train_months)
        test_start = train_end
        test_end = test_start + pd.DateOffset(months=test_months)

        if test_end > end:
            break

        windows.append({
            "train_start": train_start.strftime("%Y-%m-%d"),
            "train_end": train_end.strftime("%Y-%m-%d"),
            "test_start": test_start.strftime("%Y-%m-%d"),
            "test_end": test_end.strftime("%Y-%m-%d"),
        })

        current += pd.DateOffset(months=step_months)

    return windows


# ──────────────────────────────────────────────────────────────
# OPTIMISATION OBJECTIVE
# ──────────────────────────────────────────────────────────────

def objective_function(metrics: Dict) -> float:
    """
    Scoring function to rank parameter combinations.

    We optimise for risk-adjusted returns, NOT raw returns.
    This reduces overfitting to specific market conditions.

    Score = Sharpe × (1 - |MaxDD|/100) × sqrt(num_trades/10)

    Components:
      - Sharpe ratio: rewards consistent risk-adjusted returns
      - Drawdown penalty: penalises deep drawdowns
      - Trade count factor: penalises too few trades (might be lucky)
                            and normalises at ~10+ trades
    """
    sharpe = metrics.get("sharpe_ratio", 0)
    max_dd = abs(metrics.get("max_drawdown_pct", -50))
    num_trades = metrics.get("total_trades", 0)

    if num_trades < 3:
        return -999  # Too few trades to be meaningful

    dd_factor = max(0, 1 - max_dd / 100)  # 0 if DD = -100%, 1 if DD = 0%
    trade_factor = min(np.sqrt(num_trades / 10), 2.0)  # caps at 2.0

    score = sharpe * dd_factor * trade_factor

    return score


# ──────────────────────────────────────────────────────────────
# WALK-FORWARD ENGINE
# ──────────────────────────────────────────────────────────────

class WalkForwardOptimiser:
    """
    Runs walk-forward optimisation:
      For each window:
        1. Try all param combos on TRAIN data
        2. Pick the best combo (by objective function)
        3. Run that combo on TEST data (out-of-sample)
      Aggregate out-of-sample results = realistic performance
    """

    def __init__(
        self,
        universe_prices: Dict[str, pd.DataFrame],
        ihsg_df: pd.DataFrame,
        foreign_flows: Optional[Dict[str, pd.DataFrame]] = None,
        stock_sectors: Optional[Dict[str, str]] = None,
    ):
        self.universe_prices = universe_prices
        self.ihsg_df = ihsg_df
        self.foreign_flows = foreign_flows or {}
        self.stock_sectors = stock_sectors or {}

    def run(
        self,
        windows: List[Dict],
        param_combos: List[Dict],
        base_config: FrameworkConfig,
    ) -> Dict:
        """
        Run the full walk-forward optimisation.

        Returns:
            {
                "windows": [...],  # per-window results
                "best_params_per_window": [...],
                "oos_equity_curves": [...],
                "aggregate_metrics": {...},
                "recommended_params": {...},
            }
        """
        results = {
            "windows": [],
            "best_params_per_window": [],
            "oos_metrics": [],
        }

        for i, window in enumerate(windows):
            logger.info(
                f"\n{'='*50}\n"
                f"Window {i+1}/{len(windows)}: "
                f"Train {window['train_start']}→{window['train_end']} | "
                f"Test {window['test_start']}→{window['test_end']}\n"
                f"{'='*50}"
            )

            # ── TRAIN: find best params ──
            best_score = -999
            best_params = {}
            best_train_metrics = {}

            for j, params in enumerate(param_combos):
                cfg = apply_params_to_config(base_config, params)
                cfg.backtest.start_date = window["train_start"]
                cfg.backtest.end_date = window["train_end"]

                try:
                    engine = BacktestEngine(cfg)
                    eq, trades, metrics = engine.run(
                        self.universe_prices, self.ihsg_df,
                        self.foreign_flows, stock_sectors=self.stock_sectors,
                    )

                    score = objective_function(metrics)

                    if score > best_score:
                        best_score = score
                        best_params = params
                        best_train_metrics = metrics

                    logger.debug(
                        f"  Combo {j+1}/{len(param_combos)}: "
                        f"score={score:.3f} sharpe={metrics.get('sharpe_ratio',0):.2f}"
                    )

                except Exception as e:
                    logger.warning(f"  Combo {j+1} failed: {e}")
                    continue

            logger.info(
                f"  Best train params: {best_params} "
                f"(score={best_score:.3f}, "
                f"sharpe={best_train_metrics.get('sharpe_ratio',0):.2f})"
            )

            # ── TEST: evaluate best params on unseen data ──
            cfg = apply_params_to_config(base_config, best_params)
            cfg.backtest.start_date = window["test_start"]
            cfg.backtest.end_date = window["test_end"]

            try:
                engine = BacktestEngine(cfg)
                eq, trades, oos_metrics = engine.run(
                    self.universe_prices, self.ihsg_df,
                    self.foreign_flows, stock_sectors=self.stock_sectors,
                )

                oos_score = objective_function(oos_metrics)

                logger.info(
                    f"  OOS result: score={oos_score:.3f}, "
                    f"return={oos_metrics.get('total_return_pct',0):.1f}%, "
                    f"sharpe={oos_metrics.get('sharpe_ratio',0):.2f}, "
                    f"DD={oos_metrics.get('max_drawdown_pct',0):.1f}%"
                )

                results["windows"].append(window)
                results["best_params_per_window"].append(best_params)
                results["oos_metrics"].append(oos_metrics)

            except Exception as e:
                logger.error(f"  OOS test failed: {e}")
                continue

        # ── AGGREGATE ──
        if results["oos_metrics"]:
            results["aggregate_metrics"] = self._aggregate_oos_metrics(
                results["oos_metrics"]
            )
            results["recommended_params"] = self._recommend_params(
                results["best_params_per_window"]
            )
        else:
            results["aggregate_metrics"] = {}
            results["recommended_params"] = {}

        return results

    def _aggregate_oos_metrics(self, oos_list: List[Dict]) -> Dict:
        """Aggregate out-of-sample metrics across windows."""
        agg = {}

        numeric_keys = [
            "total_return_pct", "sharpe_ratio", "sortino_ratio",
            "max_drawdown_pct", "win_rate_pct", "profit_factor",
            "total_trades", "avg_holding_days",
        ]

        for key in numeric_keys:
            values = [m.get(key, 0) for m in oos_list if key in m]
            if values:
                agg[f"{key}_mean"] = np.mean(values)
                agg[f"{key}_std"] = np.std(values)
                agg[f"{key}_min"] = np.min(values)
                agg[f"{key}_max"] = np.max(values)

        agg["num_windows"] = len(oos_list)
        agg["avg_oos_score"] = np.mean([
            objective_function(m) for m in oos_list
        ])

        return agg

    def _recommend_params(self, params_list: List[Dict]) -> Dict:
        """
        Recommend final parameters based on what was selected
        most frequently across windows (modal values).
        This is more robust than picking the single best window's params.
        """
        if not params_list:
            return {}

        # For each parameter, find the most common value
        all_keys = set()
        for p in params_list:
            all_keys.update(p.keys())

        recommended = {}
        for key in all_keys:
            values = [p[key] for p in params_list if key in p]
            if not values:
                continue
            # Use the median for numeric values (more robust than mode)
            recommended[key] = float(np.median(values))

        return recommended


# ──────────────────────────────────────────────────────────────
# REPORT
# ──────────────────────────────────────────────────────────────

def print_optimisation_report(results: Dict):
    """Print a formatted optimisation report."""
    print("\n" + "=" * 70)
    print("  WALK-FORWARD OPTIMISATION RESULTS")
    print("=" * 70)

    # Per-window results
    if results.get("windows"):
        print("\n── PER-WINDOW OUT-OF-SAMPLE RESULTS ──")
        print(f"{'Window':<10} {'Period':<30} {'Return':>10} {'Sharpe':>10} {'MaxDD':>10} {'Trades':>8}")
        print("-" * 78)

        for i, (window, metrics) in enumerate(
            zip(results["windows"], results["oos_metrics"])
        ):
            period = f"{window['test_start']} → {window['test_end']}"
            print(
                f"  {i+1:<8} {period:<30} "
                f"{metrics.get('total_return_pct', 0):>9.1f}% "
                f"{metrics.get('sharpe_ratio', 0):>10.2f} "
                f"{metrics.get('max_drawdown_pct', 0):>9.1f}% "
                f"{metrics.get('total_trades', 0):>8}"
            )

    # Aggregate
    agg = results.get("aggregate_metrics", {})
    if agg:
        print(f"\n── AGGREGATE (across {agg.get('num_windows', 0)} windows) ──")
        print(f"  Avg OOS Return:     {agg.get('total_return_pct_mean', 0):>8.1f}% "
              f"(± {agg.get('total_return_pct_std', 0):.1f}%)")
        print(f"  Avg OOS Sharpe:     {agg.get('sharpe_ratio_mean', 0):>8.2f} "
              f"(± {agg.get('sharpe_ratio_std', 0):.2f})")
        print(f"  Avg Max Drawdown:   {agg.get('max_drawdown_pct_mean', 0):>8.1f}% "
              f"(worst: {agg.get('max_drawdown_pct_min', 0):.1f}%)")
        print(f"  Avg Win Rate:       {agg.get('win_rate_pct_mean', 0):>8.1f}%")
        print(f"  Avg Profit Factor:  {agg.get('profit_factor_mean', 0):>8.2f}")

    # Recommended params
    rec = results.get("recommended_params", {})
    if rec:
        print("\n── RECOMMENDED PARAMETERS ──")
        print("  (median of best params across all windows)")
        for key, val in sorted(rec.items()):
            print(f"  {key:<45} = {val}")

        print("\n  To apply these, update config.py or pass them programmatically:")
        print("  " + json.dumps(rec, indent=4))

    # Per-window best params
    if results.get("best_params_per_window"):
        print("\n── BEST PARAMS PER WINDOW ──")
        for i, params in enumerate(results["best_params_per_window"]):
            print(f"  Window {i+1}: {params}")

    print("\n" + "=" * 70)
    print("  INTERPRETATION GUIDE:")
    print("  • If OOS returns vary wildly across windows → strategy is fragile")
    print("  • If OOS Sharpe is consistently > 0.5 → promising robustness")
    print("  • If recommended params are similar across windows → stable edge")
    print("  • If train performance >> test performance → likely overfit")
    print("=" * 70)
    print("  DISCLAIMER: Past performance does not guarantee future results.")
    print("=" * 70)


# ──────────────────────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Walk-Forward Optimisation for IDX Swing Trader"
    )
    parser.add_argument("--start", default="2021-01-01")
    parser.add_argument("--end", default="2024-12-31")
    parser.add_argument("--db", default=DATABASE_URL)
    parser.add_argument("--param-grid", default="conservative",
                        choices=list(PARAM_GRIDS.keys()),
                        help="Which parameter grid to search")
    parser.add_argument("--train-months", type=int, default=18)
    parser.add_argument("--test-months", type=int, default=6)
    parser.add_argument("--step-months", type=int, default=6)
    parser.add_argument("--tickers", nargs="+", default=None)
    parser.add_argument("--output", default="optimisation_results.json")
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    tickers = args.tickers or LQ45_TICKERS

    # Load data
    logger.info("Loading data from database...")
    engine_db = create_all_tables(args.db)
    session = get_session(engine_db)

    start_dt = pd.Timestamp(args.start).date()
    end_dt = pd.Timestamp(args.end).date()

    universe_prices = {}
    foreign_flows = {}

    for ticker in tickers:
        pdf = load_prices_as_dataframe(session, ticker, start_dt, end_dt)
        if not pdf.empty:
            universe_prices[ticker] = pdf
        ff = load_foreign_flow_df(session, ticker, start_dt, end_dt)
        if not ff.empty:
            foreign_flows[ticker] = ff

    ihsg_df = load_index_df(session, "IHSG", start_dt, end_dt)

    logger.info(f"Loaded {len(universe_prices)} stocks, IHSG: {len(ihsg_df)} days")

    if not universe_prices:
        logger.error("No data. Run main_backtest.py --scrape first.")
        sys.exit(1)

    # Generate windows
    windows = generate_walk_forward_windows(
        args.start, args.end,
        train_months=args.train_months,
        test_months=args.test_months,
        step_months=args.step_months,
    )
    logger.info(f"Generated {len(windows)} walk-forward windows")

    if not windows:
        logger.error("No valid windows. Extend the date range.")
        sys.exit(1)

    # Generate parameter combinations
    grid = PARAM_GRIDS[args.param_grid]
    combos = generate_param_combinations(grid)
    logger.info(f"Grid '{args.param_grid}': {len(combos)} parameter combinations")

    total_runs = len(windows) * len(combos)
    logger.info(f"Total backtest runs: {total_runs} (windows × combos)")

    # Run optimisation
    optimiser = WalkForwardOptimiser(
        universe_prices, ihsg_df, foreign_flows,
    )

    base_config = FrameworkConfig()
    results = optimiser.run(windows, combos, base_config)

    # Report
    print_optimisation_report(results)

    # Save results
    # Convert non-serialisable items
    save_results = {
        "windows": results.get("windows", []),
        "best_params_per_window": results.get("best_params_per_window", []),
        "aggregate_metrics": {
            k: float(v) if isinstance(v, (np.floating, np.integer)) else v
            for k, v in results.get("aggregate_metrics", {}).items()
        },
        "recommended_params": {
            k: float(v) for k, v in results.get("recommended_params", {}).items()
        },
        "param_grid_used": args.param_grid,
        "run_date": datetime.now().isoformat(),
    }

    with open(args.output, "w") as f:
        json.dump(save_results, f, indent=2, default=str)
    logger.info(f"Results saved to {args.output}")

    session.close()


if __name__ == "__main__":
    main()
