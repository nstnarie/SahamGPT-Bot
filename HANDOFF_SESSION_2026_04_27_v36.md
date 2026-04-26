# Handoff Session 2026-04-27 — v36

## Step 19: Liquidity Filter

### What Changed

Added a liquidity filter to block signals from stocks that are too illiquid to trade realistically.

**Files modified:**
- `signals/technical.py` — added `avg_daily_value_20d` indicator: 20-day rolling mean of `close × volume`
- `signals/signal_combiner.py` — added `avg_daily_value_20d >= min_avg_daily_value` to `is_breakout` condition in `_add_breakout_signals()`
- `config.py` — `UniverseConfig.min_avg_daily_value` set to `500_000_000` (was 5B, but was dead/unenforced)

### Why

The `min_avg_daily_value` field existed in `UniverseConfig` at 5B but was never read by the signal or engine code — it was dead config. Analysis of all 181 executed trades across 2023-2025 showed that trades with avg daily value < 0.5B were genuinely untradeable at system position sizes (e.g., ARGO at Rp 40M/day), and none of the blocked trades at any threshold were big winners (>20% PnL).

### Threshold Selection

Tested 0.5B vs 1B:

| Threshold | Trades Blocked | 2023 | 2024 | 2025 |
|-----------|---------------|------|------|------|
| 1.0B | 11 trades | -6.7pp | -6.7pp | +0.4pp |
| 0.5B | 4 trades | ~0pp | -3.4pp | +0.4pp |

0.5B is the right choice: blocks only truly untradeable stocks (ARGO 0.04B, DSSA early-2024 0.18B, AGII 0.28B) while preserving BALI and others that are close to 1B.

The 2024 -3.4pp is accepted cost: the 4 blocked 2024 trades (ARGO +17%, DSSA +12%, AGII +10%, BALI Nov +9%) were good winners, but genuinely untradeable — ARGO at 0.04B, DSSA at 0.18B. In a live system these can't be entered at Rp 60M position size.

### Step 19 Results

| Year | Return | CAGR | PF | WR | Trades | Max DD | Sharpe | Calmar |
|------|--------|------|----|----|--------|--------|--------|--------|
| 2023 | +48.50% | 53.81% | 2.14 | 42.7% | 75 | -5.30% | 2.37 | 10.15 |
| 2024 | +31.05% | 34.95% | 3.30 | 53.7% | 82 | -7.11% | 1.63 | 4.92 |
| 2025 | +127.86% | 152.33% | 9.15 | 66.2% | 77 | -30.96% | 2.32 | 4.92 |

Reports: `reports_local_2023_liq05/`, `reports_local_2024_liq05/`, `reports_local_2025_liq05/`

IHSG: 2023 +6.16% | 2024 -3.33% | 2025 +20.71%

### What Was Discussed (Not Changed)

- **BRPT throttle analysis (2025-05-07, 2025-05-20):** Both signals were dropped by the rolling 10-day MPW=6 throttle, not capital or weekly limits. The April cluster (MYOR, HMSP, WIIM on 2025-04-25 + DMAS, TINS on 2025-04-28 = 5 entries, +1 AVIA on 2025-05-05 = 6 total) hit the threshold exactly when BRPT's first two signals queued. BRPT finally executed on 2025-05-22 at 1080 (+67%).

- **MPW=6 rationale:** Originally 10. Reduced to 6 in Step 8 because MPW=10 gave PF 0.81, -2.84% in 2024. MPW=6 forces composite ranking to filter false-breakout clusters in sideways regime. Tested 3/5/7/8/10 — 6 is sweet spot.

### Remaining Priorities

1. **⚠️ MANDATORY — Pre-compute `top_broker_acc` daily CSV for GitHub**
   Daily signal runs on GitHub with no broker DB. BS/TBA combined filter is a no-op in live signals.
   Fix: pre-compute `top_broker_acc` per ticker/day → `broker_acc_daily.csv` → commit to repo.
   Files: `database/data_loader.py`, `backtest/engine.py`, `signals/signal_combiner.py`.

2. **Mega winner capture rate analysis** — Cross-reference `mega_winners_analysis.xlsx` against `trade_log.csv` (all 3 years). Compute capture rate, identify which mega winners were missed and which filter blocked them.

3. **fp_ratios.json** — Needs regeneration with 2023-2025 data for CI compatibility.

4. **2021-2022 validation** — Run backtests for earlier years once price data confirmed.

5. **min_profit_to_add 15%→10%** — Lower pyramid trigger, test independently.
