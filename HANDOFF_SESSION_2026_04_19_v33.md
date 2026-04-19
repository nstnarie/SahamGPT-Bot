# Handoff — 2026-04-19 v33

## What Changed This Session

### Step 11: Signal Quality Analysis — Phase B Complete

Three improvements implemented and merged to main:

#### 1. Extreme pullback filter (BS >= -8%)
- Blocks entry when breakout_strength < -8% at T+1 open
- Quick failures average BS=-3.1% to -4.8% — they enter below the breakout level
- Cross-year safe: 0 direct big winners blocked in 2024 or 2025
- Implemented in `backtest/engine.py` (~line 170-178)
- Config: `EntryFilterConfig.min_breakout_strength = -8.0`, `use_breakout_strength_filter = True`

#### 2. Combined BS/TBA entry filter
- Blocks entry when `breakout_strength < 0 AND top_broker_acc < 0` at T+1
- BS-/TBA- quadrant: 0 direct big winners in 2024 or 2025; avg -4.2% loss
- Direct blocks: 11 (2024) + 9 (2025) trades, all losers
- Cascade effect in 2024: displaced 3×~16% BW, gained PANI +55%; net positive
- No-op in CI (top_broker_acc=0 when broker DB absent)
- Implemented in `backtest/engine.py` (~line 180-188)
- Config: `EntryFilterConfig.use_combined_bs_tba_filter = True`

#### 3. Key finding: Composite score recalibration is a no-op
- MPW=6 (rolling 10-day entry limit) never binds — max 4 signals/day observed
- Changing composite weights had zero effect on results
- Do NOT invest effort tuning composite weights

---

## Current Baselines (main, 2026-04-19)

| Year | Return | PF | WR | Trades | BW | QF | Max DD | Source |
|------|--------|----|----|--------|-----|-----|--------|--------|
| 2024 | +13.05% | 2.05 | 50.0% | 46 | 11 | 11 | -4.96% | Local |
| 2025 | +18.29% | 2.44 | 59.6% | 52 | 18 | 11 | -4.29% | Local |
| 2024 CI | +6.54% | 1.42 | — | 59 | 14 | — | — | GitHub CI |
| 2025 CI | +16.11% | 1.99 | — | 63 | 17 | — | — | GitHub CI |

Note: CI and local differ because BS/TBA filter is a no-op in CI (no broker DB). CI uses fp_ratios.json for fp_ratio filter.

### Exit breakdown (local, 2024):
TREND_EXIT: 10, STOP_LOSS: 9, TIME_EXIT: 7, PARTIAL_PROFIT: 6, EMERGENCY_STOP: 6, REGIME_EXIT: 5, FF_EXIT: 3
Avg win: +17.0%, Avg loss: -6.9%

### Exit breakdown (local, 2025):
TREND_EXIT: 18, PARTIAL_PROFIT: 11, STOP_LOSS: 11, EMERGENCY_STOP: 8, TIME_EXIT: 3, FF_EXIT: 1
Avg win: +21.8%, Avg loss: -7.8%

---

## Three Active Entry Filters

All in `config.py → EntryFilterConfig`, all have enable/disable flags:

| Filter | Config flag | Effect | CI behavior |
|--------|------------|--------|-------------|
| fp_ratio < 0.40 | `use_fp_filter` | Blocks BBCA/BMRI/BBRI/TLKM-class stocks | Uses fp_ratios.json |
| BS >= -8% | `use_breakout_strength_filter` | Blocks extreme overnight gap-downs | Active (uses sig_df) |
| BS<0 AND TBA<0 | `use_combined_bs_tba_filter` | Blocks faded breakout + selling | No-op (TBA=0) |

---

## What Was Learned About Broker Accumulation Data

1. **accumulation_score is counterintuitive as entry filter**: Winners have MORE negative acc_score (d=-0.413 in 2024). Asing brokers are often supply side at breakout — domestic buying creates the move.
2. **top_broker_acc sign is useful in combination**: TBA+ alone is moderate signal. But BS+/TBA+ quadrant = 76% WR, 0 QF — the best trade profile.
3. **BS-/TBA- is the only structural dead zone**: Both independent signals confirm weakness. No big winner has emerged from this combination in 2024 or 2025.
4. **Using BS+/TBA+ as a requirement would block too many big winners**: The middle quadrants (BS+/TBA- and BS-/TBA+) contain 16 big winners combined. Block only the dead zone.
5. **Premium data advantage**: top_broker_acc uses Stockbit premium broker_summary data. The filter provides genuine alpha unavailable to free-tier users.

---

## Locked Parameters (Do NOT Change Without Full Backtest)

| Parameter | Value | Last Tested | Result of Change |
|-----------|-------|------------|-----------------|
| min_hold_days | 5 | Step 10 | Day-4 cliff, -90M noise exits |
| emergency_stop_pct | 0.12 | Step 10 | 0.10 worsened both years |
| circuit_breaker_losses | 0 (off) | Step 8 | Cascade effect worsened results |
| breakout_period | 20 | Step 6 | 60d misses mega-winners by 21 days |
| max_entries_per_week | 6 | Step 8 | Sweet spot vs 3/5/7/8/10 |
| SIDEWAYS mult | 0.5 | Step 11 | 1.0 doubled DD in 2024 |
| partial_sell_fraction | 0.30 | Step 11 | 0.0 dropped BW 14→8, WR -7pts |
| breakout_strength filter | -8.0 | Step 11 | >= 0 blocks 50% of big winners |

---

## Next Steps

### Step 2: Exit improvements
Current exit breakdown shows potential issues:
- **EMERGENCY_STOP**: 6 (2024) + 8 (2025) trades — do these fire on recoverable dips?
- **TIME_EXIT**: 7 (2024) + 3 (2025) — are these truly stalled or would they recover?
- **STOP_LOSS**: 9 (2024) + 11 (2025) — any systematic patterns (day of week, regime)?

Approach: analyze trade_log.csv exit patterns before designing any changes. Read actual exit conditions in `backtest/portfolio.py` first.

### Step 3: 2021-2023 validation
Filters validated on 2024 (bear) and 2025 (bull). Need to check if BS/TBA filter holds in 2021-2023 data before treating it as structurally proven.

---

## Git State

- Branch: `main`
- Latest commit: `b4a680f` — "Add combined BS/TBA entry filter (Step 11)"
- Previous: `a802c64` — "Add extreme pullback filter (Step 11)"

No open experiment branches.
