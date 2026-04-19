# Handoff — 2026-04-19 v35

## What Changed This Session

### Step 13: New High Pyramid Trigger

**Problem**: Pyramiding (Step 12) only fired on full `is_breakout` signals — requiring close > 20-day high AND volume >= 1.5x average. Slow grinders like PTRO 2024 (+42%, 40-day hold) never triggered pyramid adds despite being in trend mode the entire time. Volume never spiked >= 1.5x during the hold. Result: ~4 pyramid adds in 2024 vs ~19 in 2025.

**Fix**: For pyramid adds only, also allow triggering on a new 20-day high without the volume requirement. Initial entries still require the full breakout signal. Position must still be in trend mode (+15%).

**Logic**: `pos.in_trend_mode AND (is_breakout OR close > high_Nd)`

**Rationale**: Volume confirmation is critical for initial entries (filtering noise). For pyramid adds to proven winners (+15%), the trend is already established — a new 20-day high is sufficient price confirmation.

### Files changed

| File | Change |
|------|--------|
| `config.py` | Added `use_new_high_trigger: bool = True` to `PyramidConfig` |
| `backtest/engine.py` | Added `_is_new_high()` helper; modified pyramid trigger to OR new-high check |

---

## Current Baselines (main, 2026-04-19, Step 13)

| Year | Return | PF | WR | Trades | Max DD | Source |
|------|--------|----|----|--------|--------|--------|
| 2024 | +17.77% | 2.32 | 47.8% | 46 | -6.70% | Local |
| 2025 | +40.97% | 4.18 | 59.6% | 52 | -7.44% | Local |

### Step-by-step progression

| Step | 2024 Return | 2024 PF | 2025 Return | 2025 PF |
|------|------------|---------|------------|---------|
| Baseline (Step 9) | +13.05% | 2.05 | +18.29% | 2.44 |
| Step 10: fp_ratio filter | — | 1.34 | — | — |
| Step 11: BS/TBA filter | +13.05% | 2.05 | +18.29% | 2.44 |
| Step 12: Pyramiding (vol-based) | +14.40% | 2.06 | +39.53% | 4.07 |
| **Step 13: New-high trigger** | **+17.77%** | **2.32** | **+40.97%** | **4.18** |

IHSG 2024: -3.33% | IHSG 2025: +20.71%

---

## Next Steps

### ⚠️ MANDATORY (do before trusting live signals)

**Pre-compute `top_broker_acc` daily CSV**

The daily signal runs on GitHub (cron 16:35 WIB) with no access to `idx_swing_trader.db`. This means `top_broker_acc = 0` for all tickers in live signals, making the BS/TBA combined filter a no-op.

Fix: pre-compute `top_broker_acc` per ticker per day → `broker_acc_daily.csv` → commit to repo → engine loads as fallback.

Pattern to follow: `fp_ratios.json` + `EntryFilterConfig.use_fp_filter` fallback in `backtest/engine.py`.
Files: `database/data_loader.py` (pre-compute), `backtest/engine.py` (load fallback), `signals/signal_combiner.py` (inject).

### Optional

1. **Lower `min_profit_to_add` from 15% to 10%** — separate experiment, test independently
2. **2021-2023 validation** — verify filters + pyramiding don't worsen bear/sideways regimes

---

## Git State

- Branch: `main`
- Latest commit: `c8d5d47` — "Add new-high pyramid trigger (Step 13)"
- Previous: `b7f2d3b` — "Flag mandatory pre-compute task for top_broker_acc"
