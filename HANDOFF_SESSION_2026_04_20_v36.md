# HANDOFF — 2026-04-20 v36 (Step 14 Analysis)

## What Happened This Session

### Step 13 (completed, on main, commit 75c1954)
- Added new-high pyramid trigger: pyramid adds also fire on `close > high_20d` (no vol req)
- 2024: +14.40% → +17.77%, PF 2.06 → 2.32
- 2025: +39.53% → +40.97%, PF 4.07 → 4.18

### Step 14: Signal Funnel Diagnostic (implemented, NOT committed)

Added full signal tracking to `backtest/engine.py`. Every BUY signal now records its fate:
- `queued` → `throttle` / `cooldown` / `gap_down` / `gap_up` / `bs_filter` / `bs_tba_filter` / `no_cash` / `size_too_small` / `max_daily` / `already_held` / `executed`

Output: `reports_local_YYYY/signal_funnel.csv`

**`main_backtest.py`** updated to handle 4th return value and save CSV.

Signal funnel counts: 2024 = 65 signals, 2025 = 82 signals.

## Critical Finding: Root Cause of Low 2024 Returns

### User Identified the Real Problem
The system returned only +17.77% in 2024 despite 66 stocks making >50% moves. The user correctly identified this: the problem is NOT reducing losers — it's missing mega winners entirely.

### Investigation: TINS (confirmed by user data)
User claimed TINS had 8x volume on March 8 breakout. Investigation confirmed:
- March 8, 2024: close=730, broke 20d high (615), volume=175M = **11.5x average** ✅ (user was right)
- **Blocked by**: `volume_spike_max=5.0` (11.5x > 5.0) AND `fp_ratio=0.403 ≥ 0.40`
- Had 12 near-breakout days — ALL blocked by one filter or another

### Full Mega Winner Analysis (All 66 Stocks)

49 out of 66 mega winners generated ZERO signals. 17 made it to the funnel. Only 14 were traded.

**The Three Killer Filters:**

| Filter | Mega Winners Blocked | % of 66 |
|--------|---------------------|---------|
| `volume_spike_max = 5.0` | **41** | 62% |
| `fp_ratio ≥ 0.40` | **36** | 55% |
| `min_stock_price = 150` | ~8 | ~12% |
| `MA200 < -10%` | 17 | 26% |

**fp_ratio filter is over-blocking**: Threshold of 0.40 was designed for BBCA(0.82)/BMRI(0.78)/BBRI(0.72). But it blocks 36 legitimate mega winners: TPIA+250%(0.525), BREN+182%(0.549), BRIS+96%(0.462), JPFA+92%(0.517), ADRO+85%(0.450), etc.

**volume_spike_max is killing institutional breakouts**: Mega winner trough breakouts are inherently high volume. TINS=11.5x, NIKL=12.6x, JARR=13.7x (first breakout), WTON=11.1x. The 5x cap treats these as pump-and-dumps.

## Current State of Working Tree

**NOT committed to main**:
- `backtest/engine.py` — signal funnel tracking
- `main_backtest.py` — 4th return value + CSV save

To commit these: `git add backtest/engine.py main_backtest.py && git commit -m "Step 14: signal funnel diagnostic"`

## Baselines (Step 13, on main)

| Year | Return | PF | WR | Trades | Max DD |
|------|--------|----|----|--------|--------|
| 2024 | +17.77% | 2.32 | 47.8% | 46 | -6.70% |
| 2025 | +40.97% | 4.18 | 59.6% | 52 | -7.44% |

## Next Steps: Phase 2 Experiments

Run these IN ORDER. Test both 2024 + 2025 for each. Accept only if both improve or one improves / other neutral.

### Experiment 1: Raise volume_spike_max from 5.0 → 10.0

```python
# config.py, BreakoutConfig:
volume_spike_max: float = 10.0  # was 5.0
```

**Rationale**: Blocks 41/66 mega winners. Mega winner trough breakouts are genuinely high-volume institutional events, not pumps. The entry filters (fp_ratio, BS/TBA, breakout_strength) catch actual pumps after they fade.

**Expected impact**: More signals generated for TINS, NIKL, JARR, PTRO (first wave), WTON, WSBP, LINK, BALI, DOID, ESSA, SMDR, AGRO, BNBA.

**Risk**: May let through more pump-and-dump entries. Monitor WR and max DD.

### Experiment 2: Raise fp_ratio threshold from 0.40 → 0.55

```python
# config.py, EntryFilterConfig:
max_fp_ratio: float = 0.55  # was 0.40
```

**Rationale**: Real hedge vehicles are BBCA(0.82)/BMRI(0.78)/BBRI(0.72)/TLKM. The 0.40 threshold over-fires, blocking 36 mega winners with 0.40-0.55 fp.

**Expected impact**: Opens up TINS(0.403), TPIA(0.525), BREN(0.549), BRIS(0.462), ENRG(0.445), KIJA(0.457), ADRO(0.450), EMTK(0.426), SCMA(0.445), ARTO(0.433).

**Risk**: fp_ratio analysis showed clear separation: low-fp=52% WR vs high-fp=32% WR, but threshold may be more gradual. Stocks in the 0.40-0.55 band may be mixed.

### Experiment 3 (optional): Lower min_stock_price from 150 → 75

```python
# config.py, UniverseConfig:
min_stock_price: float = 75.0  # was 150.0
```

**Rationale**: Blocks DEWA+164%(all near-BOs at 60-130), INET+90%, ALTO+150%, WSBP+160%.

**Risk**: Low-priced stocks have wider spreads, slippage model may not capture true cost.

### Experiment 4: Combine Experiments 1+2

After individual tests, if both help, combine for cumulative effect.

## Architecture (Quick Reference)

```
config.py:
  BreakoutConfig.breakout_period = 20
  BreakoutConfig.volume_spike_min = 1.5
  BreakoutConfig.volume_spike_max = 5.0  ← EXPERIMENT 1
  EntryFilterConfig.max_fp_ratio = 0.40  ← EXPERIMENT 2
  EntryFilterConfig.min_price_vs_ma200 = -10.0
  EntryFilterConfig.min_atr_pct = 1.75
  UniverseConfig.min_stock_price = 150   ← EXPERIMENT 3

signals/signal_combiner.py:_add_breakout_signals():
  Line 117-157: All signal-level filters applied here
  Line 151-152: fp_ratio filter — blocks entire ticker if fp >= max_fp_ratio

backtest/engine.py:
  Signal funnel appended at BUY signal detection
  Fate updated at each block point in entry execution
  Returns (equity_curve, trade_log, metrics, signal_funnel_df)
```

## Mandatory Pending (from Step 13)

**Pre-compute `broker_acc_daily.csv`** — BS/TBA filter is no-op in live GitHub signals because no broker DB is available. Daily Telegram signals may include BS-/TBA- losers (~19% WR). Fix by pre-computing top_broker_acc per ticker per day from local DB → commit CSV → engine loads as fallback (same pattern as fp_ratios.json).
