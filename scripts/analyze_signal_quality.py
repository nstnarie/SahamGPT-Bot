"""
Signal Quality Analysis — Step 11
===================================
Reads an enhanced trade_log.csv (with entry-time signal features) and
produces a comprehensive markdown report comparing winners vs losers,
identifying optimal entry filter thresholds, and cross-referencing
mega-winner capture.

Usage:
    python scripts/analyze_signal_quality.py \
        --trade-log reports/trade_log.csv \
        --output reports/signal_quality_analysis.md \
        [--big-winner-pct 15]
"""

import argparse
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats


# ── Signal features to analyse ────────────────────────────────────────────────

SIGNAL_FEATURES = [
    ("composite_score",   "Composite score (0-1, higher=better signal quality)"),
    ("breakout_strength", "Breakout strength (% above 20d high)"),
    ("vol_ratio",         "Volume ratio (current / 20d avg)"),
    ("rsi",               "RSI(14) at entry"),
    ("atr_pct",           "ATR% (ATR / price × 100)"),
    ("price_vs_ma200",    "Price vs MA200 (%)"),
    ("prior_return_5d",   "5-day prior return (%)"),
    ("accumulation_score","Broker accumulation score (count-based)"),
    ("top_broker_acc",    "Top-5 Asing value-weighted accumulation"),
    ("net_foreign",       "Net foreign flow on entry day (IDR)"),
    ("ff_confirmed",      "FF confirmed (1=yes, 0=no)"),
    ("ksei_net_5d",       "KSEI 5-day net flow (IDR)"),
    ("dist_from_52w_high","Distance from 52-week high (%)"),
    ("entry_exposure_mult","Regime exposure multiplier at entry"),
]

FEATURE_COLS = [f for f, _ in SIGNAL_FEATURES]


def cohen_d(a, b):
    """Cohen's d effect size between two arrays."""
    na, nb = len(a), len(b)
    if na < 2 or nb < 2:
        return float("nan")
    pooled_sd = math.sqrt(((na - 1) * a.std(ddof=1) ** 2 + (nb - 1) * b.std(ddof=1) ** 2) / (na + nb - 2))
    if pooled_sd == 0:
        return float("nan")
    return (a.mean() - b.mean()) / pooled_sd


def mannwhitney_p(a, b):
    """Mann-Whitney U p-value (two-sided)."""
    if len(a) < 2 or len(b) < 2:
        return float("nan")
    try:
        _, p = stats.mannwhitneyu(a, b, alternative="two-sided")
        return p
    except Exception:
        return float("nan")


def feature_table(group_a, group_b, label_a, label_b, lines):
    """Append a feature-by-feature comparison table to lines."""
    lines.append(f"| Feature | {label_a} mean | {label_b} mean | Cohen's d | p-value | Significant? |")
    lines.append("|---------|" + "--------|" * 5)
    results = []
    for col, desc in SIGNAL_FEATURES:
        if col not in group_a.columns:
            continue
        a = group_a[col].dropna()
        b = group_b[col].dropna()
        if len(a) < 3 or len(b) < 3:
            continue
        d = cohen_d(a, b)
        p = mannwhitney_p(a, b)
        results.append((col, desc, a.mean(), b.mean(), d, p))

    results.sort(key=lambda x: abs(x[4]) if not math.isnan(x[4]) else 0, reverse=True)
    for col, desc, mean_a, mean_b, d, p in results:
        sig = "✓" if (not math.isnan(p) and p < 0.05) else ""
        d_str = f"{d:+.3f}" if not math.isnan(d) else "N/A"
        p_str = f"{p:.3f}" if not math.isnan(p) else "N/A"
        lines.append(f"| {col} | {mean_a:.3f} | {mean_b:.3f} | {d_str} | {p_str} | {sig} |")
    lines.append("")
    return results


def threshold_sweep(df, col, big_winner_pct, direction="above"):
    """
    Sweep thresholds for `col`. For each threshold:
    - Compute trades blocked, big winners blocked, remaining PF.
    direction='above': block if col < threshold (higher=better)
    direction='below': block if col > threshold (lower=better)
    Returns list of dicts.
    """
    valid = df[col].dropna()
    if len(valid) < 10:
        return []

    pct_range = np.linspace(valid.quantile(0.05), valid.quantile(0.95), 20)
    rows = []
    total_bw = (df["pnl_pct"] >= big_winner_pct).sum()
    wins = df[df["pnl"] > 0]["pnl"].sum()
    losses = abs(df[df["pnl"] <= 0]["pnl"].sum())
    baseline_pf = wins / losses if losses > 0 else float("inf")

    for thresh in pct_range:
        if direction == "above":
            kept = df[df[col].fillna(thresh) >= thresh]
            blocked = df[df[col].fillna(thresh) < thresh]
        else:
            kept = df[df[col].fillna(thresh) <= thresh]
            blocked = df[df[col].fillna(thresh) > thresh]

        bw_lost = (blocked["pnl_pct"] >= big_winner_pct).sum()
        if len(kept) == 0:
            continue
        k_wins = kept[kept["pnl"] > 0]["pnl"].sum()
        k_losses = abs(kept[kept["pnl"] <= 0]["pnl"].sum())
        kept_pf = k_wins / k_losses if k_losses > 0 else float("inf")
        kept_wr = (kept["pnl"] > 0).mean() * 100

        rows.append({
            "threshold": thresh,
            "blocked": len(blocked),
            "bw_blocked": bw_lost,
            "kept": len(kept),
            "kept_wr": kept_wr,
            "kept_pf": kept_pf,
            "pf_delta": kept_pf - baseline_pf,
        })
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--trade-log", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--big-winner-pct", type=float, default=15.0)
    args = parser.parse_args()

    csv_path = Path(args.trade_log)
    if not csv_path.exists():
        print(f"ERROR: {csv_path} not found", file=sys.stderr)
        sys.exit(1)

    df = pd.read_csv(csv_path)
    if df.empty:
        print("Trade log is empty", file=sys.stderr)
        sys.exit(0)

    df["pnl"] = pd.to_numeric(df["pnl"], errors="coerce")
    df["pnl_pct"] = pd.to_numeric(df["pnl_pct"], errors="coerce")
    df["holding_days"] = pd.to_numeric(df["holding_days"], errors="coerce")
    df["entry_date"] = pd.to_datetime(df["entry_date"])

    for col in FEATURE_COLS:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    BW = args.big_winner_pct
    winners = df[df["pnl"] > 0]
    losers = df[df["pnl"] <= 0]
    big_winners = df[df["pnl_pct"] >= BW]
    non_bw = df[df["pnl_pct"] < BW]
    quick_fails = df[
        df["exit_reason"].isin(["STOP_LOSS", "EMERGENCY_STOP"]) & (df["holding_days"] <= 8)
    ]
    non_stop = df[~df["exit_reason"].isin(["STOP_LOSS", "EMERGENCY_STOP"])]

    signal_cols_present = [c for c in FEATURE_COLS if c in df.columns and df[c].notna().sum() > 5]

    lines = []
    lines.append("# Signal Quality Analysis")
    lines.append(f"Generated from: {csv_path.name}")
    lines.append(f"Total trades: {len(df)} | Winners: {len(winners)} ({len(winners)/len(df)*100:.1f}%) | Losers: {len(losers)}")
    lines.append(f"Big winners (≥{BW:.0f}%): {len(big_winners)} | Quick failures (SL/EMG ≤8d): {len(quick_fails)}")
    lines.append(f"Signal features available: {len(signal_cols_present)}")
    lines.append("")

    if not signal_cols_present:
        lines.append("**No signal features found in trade log.** Run backtest with enhanced trade log first.")
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text("\n".join(lines))
        print("No signal features — output written with warning")
        return

    # ── Section 1: Winners vs Losers ─────────────────────────────────────────
    lines.append("## 1. Feature Comparison: Winners vs Losers")
    lines.append(f"*Winners (n={len(winners)}) vs Losers (n={len(losers)})*")
    lines.append("")
    lines.append("Positive Cohen's d = feature is HIGHER for winners (good for entry filter direction).")
    lines.append("Negative Cohen's d = feature is LOWER for winners.")
    lines.append("")
    w_vs_l = feature_table(winners, losers, f"Winners(n={len(winners)})", f"Losers(n={len(losers)})", lines)

    # ── Section 2: Big Winners vs Rest ────────────────────────────────────────
    lines.append(f"## 2. Feature Comparison: Big Winners (≥{BW:.0f}%) vs Rest")
    lines.append(f"*Big winners (n={len(big_winners)}) vs Non-big-winners (n={len(non_bw)})*")
    lines.append("")
    bw_vs_rest = feature_table(big_winners, non_bw, f"BigWin(n={len(big_winners)})", f"Rest(n={len(non_bw)})", lines)

    # ── Section 3: Quick Failures vs Non-Stop Exits ───────────────────────────
    lines.append("## 3. Feature Comparison: Quick Failures vs Non-Stop Exits")
    lines.append(f"*Quick failures SL/EMG ≤8d (n={len(quick_fails)}) vs Non-stop exits (n={len(non_stop)})*")
    lines.append("")
    lines.append("Negative Cohen's d here means false breakouts have LOWER feature values.")
    lines.append("")
    qf_vs_ns = feature_table(non_stop, quick_fails, f"NonStop(n={len(non_stop)})", f"QuickFail(n={len(quick_fails)})", lines)

    # ── Section 4: Regime-Conditioned Analysis ────────────────────────────────
    if "entry_regime" in df.columns:
        lines.append("## 4. Regime-Conditioned Analysis")
        lines.append("| Regime | Trades | WR | PF | Avg PnL% | Big Winners |")
        lines.append("|--------|--------|----|-----|---------|------------|")
        for regime, grp in df.groupby("entry_regime"):
            if len(grp) < 2:
                continue
            wr = (grp["pnl"] > 0).mean() * 100
            gw = grp[grp["pnl"] > 0]["pnl"].sum()
            gl = abs(grp[grp["pnl"] <= 0]["pnl"].sum())
            pf = gw / gl if gl > 0 else float("inf")
            bw_count = (grp["pnl_pct"] >= BW).sum()
            lines.append(f"| {regime or 'unknown'} | {len(grp)} | {wr:.0f}% | {pf:.2f} | {grp['pnl_pct'].mean():+.1f}% | {bw_count} |")
        lines.append("")

    # ── Section 5: Composite Score Calibration ────────────────────────────────
    if "composite_score" in df.columns and df["composite_score"].notna().sum() > 10:
        lines.append("## 5. Composite Score Calibration (Quintiles)")
        lines.append("Tests whether the existing ranking score predicts trade quality.")
        lines.append("")
        lines.append("| Score Quintile | Trades | WR | PF | Avg PnL% | Big Winners |")
        lines.append("|----------------|--------|----|-----|---------|------------|")
        df["score_q"] = pd.qcut(df["composite_score"].dropna(), 5, labels=["Q1(low)", "Q2", "Q3", "Q4", "Q5(high)"], duplicates="drop")
        for q, grp in df.groupby("score_q", observed=True):
            if len(grp) < 2:
                continue
            wr = (grp["pnl"] > 0).mean() * 100
            gw = grp[grp["pnl"] > 0]["pnl"].sum()
            gl = abs(grp[grp["pnl"] <= 0]["pnl"].sum())
            pf = gw / gl if gl > 0 else float("inf")
            bw_count = (grp["pnl_pct"] >= BW).sum()
            lines.append(f"| {q} | {len(grp)} | {wr:.0f}% | {pf:.2f} | {grp['pnl_pct'].mean():+.1f}% | {bw_count} |")
        lines.append("")

    # ── Section 6: Threshold Sweep for Top Features ───────────────────────────
    lines.append("## 6. Threshold Sweep — Top Discriminating Features")
    lines.append("For each feature, find thresholds that block losers while preserving big winners.")
    lines.append("`bw_blocked=0` rows are safe to consider as entry filters.")
    lines.append("")

    # Collect top features from winners-vs-losers (by |d|)
    top_features = [
        (col, d, desc)
        for col, desc, ma, mb, d, p in w_vs_l
        if not math.isnan(d) and col in df.columns
    ]
    top_features.sort(key=lambda x: abs(x[1]), reverse=True)

    for col, d, desc in top_features[:6]:
        direction = "above" if d > 0 else "below"
        sweep = threshold_sweep(df, col, BW, direction=direction)
        if not sweep:
            continue

        lines.append(f"### {col} (Cohen's d={d:+.3f}, filter direction: {direction})")
        lines.append(f"_{desc}_")
        lines.append("")
        lines.append("| Threshold | Blocked | BW Blocked | Kept | Kept WR | Kept PF | PF delta |")
        lines.append("|-----------|---------|-----------|------|---------|---------|---------|")
        for r in sweep:
            safe_mark = " ✓" if r["bw_blocked"] == 0 else ""
            lines.append(
                f"| {r['threshold']:.3f} | {r['blocked']} | {r['bw_blocked']}{safe_mark} | "
                f"{r['kept']} | {r['kept_wr']:.0f}% | {r['kept_pf']:.2f} | {r['pf_delta']:+.2f} |"
            )
        lines.append("")

    # ── Section 7: Most-Traded Ticker Analysis ────────────────────────────────
    lines.append("## 7. Most-Traded Tickers (Multi-Trade Analysis)")
    lines.append("| Ticker | Trades | WR | Avg PnL% | Total PnL | Exit Mix |")
    lines.append("|--------|--------|----|---------|---------|---------|")
    multi = df.groupby("ticker").filter(lambda x: len(x) >= 2)
    if len(multi) > 0:
        for ticker, grp in multi.groupby("ticker"):
            wr = (grp["pnl"] > 0).mean() * 100
            exit_mix = ", ".join(f"{r}×{c}" for r, c in grp["exit_reason"].value_counts().items())
            lines.append(f"| {ticker} | {len(grp)} | {wr:.0f}% | {grp['pnl_pct'].mean():+.1f}% | Rp {grp['pnl'].sum():+,.0f} | {exit_mix} |")
    lines.append("")

    # ── Section 8: Summary — Actionable Findings ─────────────────────────────
    lines.append("## 8. Summary — Key Findings")
    lines.append("")

    # Strongest discriminator (winners vs losers)
    if w_vs_l:
        col, desc, ma, mb, d, p = w_vs_l[0]
        lines.append(f"**Strongest winner/loser discriminator**: `{col}` (Cohen's d={d:+.3f})")
        lines.append(f"  Winners avg {ma:.3f} vs Losers avg {mb:.3f}")
        lines.append("")

    # Strongest quick-fail discriminator
    if qf_vs_ns:
        col, desc, ma, mb, d, p = qf_vs_ns[0]
        lines.append(f"**Strongest quick-failure discriminator**: `{col}` (Cohen's d={d:+.3f})")
        lines.append(f"  Non-stop avg {ma:.3f} vs Quick-fail avg {mb:.3f}")
        lines.append("")

    # Big winner features
    if bw_vs_rest:
        col, desc, ma, mb, d, p = bw_vs_rest[0]
        lines.append(f"**Strongest mega-winner predictor**: `{col}` (Cohen's d={d:+.3f})")
        lines.append(f"  Big winners avg {ma:.3f} vs Rest avg {mb:.3f}")
        lines.append("")

    # Features significant at p<0.05 AND |d|>0.2
    actionable = [
        (col, d, p)
        for col, desc, ma, mb, d, p in w_vs_l
        if not math.isnan(d) and abs(d) > 0.2 and not math.isnan(p) and p < 0.05
    ]
    if actionable:
        lines.append(f"**Features with |d|>0.2 AND p<0.05 (winners vs losers):**")
        for col, d, p in actionable:
            lines.append(f"  - `{col}`: d={d:+.3f}, p={p:.3f}")
        lines.append("")
    else:
        lines.append("**No features with |d|>0.2 AND p<0.05** — consider combining features or using different groupings.")
        lines.append("")

    report = "\n".join(lines)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(report)
    print(f"Signal quality analysis written to {output_path}")
    print(report[:3000])  # Preview first 3000 chars


if __name__ == "__main__":
    main()
